import json
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from azure.eventhub import EventHubProducerClient, EventData
from azure.eventhub.exceptions import EventHubError
from config_service import EventStreamConfig
from sqlalchemy.exc import IntegrityError

from retry_handler import default_retry_handler, eventstream_circuit_breaker
from models import EventStreamMetrics, SystemHealth
from extensions import db

logger = logging.getLogger(__name__)


class EventStreamClient:
    def __init__(self, app=None, config: EventStreamConfig | None = None):
        self.producer = None
        self.connection_status = 'unknown'
        self.last_successful_send = None
        self.config = config
        self._lock = threading.Lock()  # thread safety
        self._shutdown = False
        self.app = app
        logger.info("EventStreamClient initialized with config snapshot")

    def _initialize_producer(self):
        """Initialize EventHub producer client with stored config."""
        if self.producer:
            return  # already initialized
        try:
            if not self.config:
                logger.warning("No EventStream configuration provided")
                self.connection_status = "not_configured"
                return

            self.producer = EventHubProducerClient.from_connection_string(
                conn_str=self.config.connection_string
            )
            self.connection_status = 'connected'
            logger.info("EventStream producer client initialized successfully")
        except Exception as e:
            self.connection_status = 'failed'
            logger.error(f"Failed to initialize EventStream producer: {str(e)}")
            self.producer = None

    def _ensure_producer(self):
        with self._lock:
            if self._shutdown:
                raise Exception("Client is shutting down")
            if not self.producer:
                self._initialize_producer()

    #@default_retry_handler.retry_with_backoff("EventStream send")
    @default_retry_handler.retry_with_backoff("EventStream send")
    def send_to_eventstream(
        self,
        payload: Dict[str, Any],
        webhook_log_id: Optional[int] = None
    ) -> bool:
        """Send payload to EventStream with retry logic and monitoring."""

        # Abort immediately if shutdown is in progress
        if getattr(self, "_shutdown", False):
            logger.info("Shutdown in progress — aborting retry")
            raise Exception("Shutdown in progress")

        self._ensure_producer()

        start_time = datetime.utcnow()
        attempt_number = 1

        metrics = EventStreamMetrics(
            webhook_log_id=webhook_log_id,
            attempt_number=attempt_number,
            payload_preview=self._create_payload_preview(payload)
        )

        try:
            # Use circuit breaker for additional protection
            eventstream_circuit_breaker.call(self._send_single_event, payload)

            # Reset breaker after success
            eventstream_circuit_breaker.reset()

            end_time = datetime.utcnow()
            metrics.success = True
            metrics.transmission_time_ms = (end_time - start_time).total_seconds() * 1000

            self.last_successful_send = end_time
            self.connection_status = 'healthy'

            payload_size = len(json.dumps(payload, default=str))
            logger.info(f"Successfully sent payload to EventStream. Size: {payload_size} bytes")
            logger.debug(f"[SEND] attempt {attempt_number} for webhook_log_id={webhook_log_id}")

            return True

        except Exception as e:
            # Special-case shutdown so retries stop immediately
            if "Shutdown in progress" in str(e):
                logger.info("Retry aborted: client is shutting down")
                return False

            end_time = datetime.utcnow()
            metrics.success = False
            metrics.error_type = type(e).__name__
            metrics.error_message = str(e)[:1000]
            metrics.transmission_time_ms = (end_time - start_time).total_seconds() * 1000

            self.connection_status = 'error'
            logger.error(f"Failed to send payload to EventStream: {str(e)}")

            # try reconnect if producer is broken
            with self._lock:
                #self.producer = None
                if self.producer:
                    try:
                        self.producer.close()
                    except Exception as e:
                        logger.warning(f"Error while closing producer: {e}")
                    finally:
                        self.producer = None

            raise

        finally:
            if self.app:
                with self.app.app_context():
                    try:
                        # --- Save metrics history ---
                        existing = None
                        if webhook_log_id:
                            existing = EventStreamMetrics.query.filter_by(
                                webhook_log_id=webhook_log_id
                            ).first()

                        if existing:
                            existing.success = metrics.success
                            existing.error_type = metrics.error_type
                            existing.error_message = metrics.error_message
                            existing.transmission_time_ms = metrics.transmission_time_ms
                            existing.payload_preview = metrics.payload_preview
                        else:
                            db.session.add(metrics)

                        # --- Update rolling system health snapshot ---
                        health = SystemHealth.query.order_by(SystemHealth.timestamp.desc()).first()
                        if not health:
                            health = SystemHealth()
                            db.session.add(health)

                        health.eventstream_connection_status = self.connection_status
                        health.last_webhook_log_id = webhook_log_id
                        health.last_payload_preview = metrics.payload_preview
                        health.last_error_message = metrics.error_message
                        health.last_attempt_time = datetime.utcnow()
                        if metrics.success:
                            health.last_successful_transmission = self.last_successful_send

                        db.session.commit()

                    except IntegrityError:
                        db.session.rollback()
                        logger.warning(f"Duplicate metrics for webhook_log_id={webhook_log_id}, skipped insert")
                    except Exception as db_error:
                        db.session.rollback()
                        logger.error(f"Failed to save EventStream metrics/SystemHealth: {str(db_error)}")


    def _send_single_event(self, payload: Dict[str, Any]):
        """Send single event to EventHub (internal method)."""
        if not self.producer:
            raise Exception("EventHub producer not initialized")

        try:
            event_data = EventData(json.dumps(payload, default=str))
            event_data.properties = {
                'source': 'kobodata',
                'timestamp': datetime.utcnow().isoformat(),
                'content_type': 'application/json'
            }

            event_batch = self.producer.create_batch()
            event_batch.add(event_data)
            self.producer.send_batch(event_batch)

            logger.debug(f"Event sent successfully: {payload.get('_id', 'unknown')}")
            self.connection_status = "healthy"
        except EventHubError as e:
            logger.error(f"EventHub specific error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error sending event: {str(e)}")
            raise

    def _create_payload_preview(self, payload: Dict[str, Any], max_fields: int = 5) -> Dict[str, Any]:
        """Create a preview of the payload for storage (first few fields only)."""
        preview = {}
        count = 0

        for key, value in payload.items():
            if count >= max_fields:
                break

            if isinstance(value, (str, int, float, bool)):
                preview[key] = value
            elif isinstance(value, dict):
                preview[key] = f"<dict with {len(value)} keys>"
            elif isinstance(value, list):
                preview[key] = f"<list with {len(value)} items>"
            else:
                preview[key] = f"<{type(value).__name__}>"

            count += 1

        if len(payload) > max_fields:
            preview['_truncated'] = f"... and {len(payload) - max_fields} more fields"

        return preview

    
    def health_check(self, deep: bool = False) -> Dict[str, Any]:
        """Perform health check. If deep=True, attempt a dummy send."""

        # Default status
        if self.connection_status == "unknown":
            if self.last_successful_send:
                status = "healthy"
            else:
                status = "unchecked"
        elif self.connection_status in ("connected", "healthy"):
            logger.info("Good news is here.")
            status = "healthy"
        elif self.connection_status in ("failed", "error"):
            logger.info("Health issue failed or error.")
            status = "unhealthy"
        elif self.connection_status == "shutdown":
            status = "shutdown"
        elif self.connection_status == "not configured":
            status = "not configured"

        health_info = {
            "status": status,
            "last_successful_send": self.last_successful_send.isoformat() if self.last_successful_send else None,
            "producer_initialized": self.producer is not None,
            "circuit_breaker_state": eventstream_circuit_breaker.state,
            "circuit_breaker_failures": eventstream_circuit_breaker.failure_count,
        }

        try:
            if self.producer:
                if deep:
                    # try dummy send
                    test_event = EventData(json.dumps({"health_check": True}))
                    batch = self.producer.create_batch()
                    batch.add(test_event)
                    self.producer.send_batch(batch)
                    health_info["connection_test"] = "passed (deep)"
                    self.connection_status = "healthy"
                else:
                    self.producer.create_batch()
                    health_info["connection_test"] = "passed"
            else:
                health_info["connection_test"] = "skipped: producer not initialized"
        except Exception as e:
            health_info["connection_test"] = f"failed: {str(e)}"
            health_info["status"] = "unhealthy"

        return health_info

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of EventStream transmission metrics."""
        try:
            recent_metrics = db.session.query(EventStreamMetrics) \
                .filter(EventStreamMetrics.timestamp >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)) \
                .all()

            total_attempts = len(recent_metrics)
            successful_attempts = sum(1 for m in recent_metrics if m.success)

            if total_attempts > 0:
                success_rate = (successful_attempts / total_attempts) * 100
                avg_transmission_time = sum(m.transmission_time_ms or 0 for m in recent_metrics) / total_attempts
            else:
                success_rate = 0
                avg_transmission_time = 0

            return {
                'total_attempts_today': total_attempts,
                'successful_attempts_today': successful_attempts,
                'success_rate_percent': round(success_rate, 2),
                'average_transmission_time_ms': round(avg_transmission_time, 2),
                'last_error': recent_metrics[-1].error_message if recent_metrics and not recent_metrics[-1].success else None
            }

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {str(e)}")
            return {'error': str(e)}


    def shutdown(self):
        """Cleanly stop retries and close the producer."""
        logger.info("Shutting down EventStream client...")
        print("Print self.producer:",self.producer)
        with self._lock:
            self._shutdown = True

            print("Print self.producer:",self.producer)
            
            if self.producer is None:
                logger.debug("No active producer to close")
            else:
                try:
                    self.producer.close()
                    logger.info("EventStream producer closed cleanly")
                except Exception as e:
                    logger.warning(f"Error closing EventStream producer: {e}")
                finally:
                    self.producer = None

            self.connection_status = "shutdown"

_eventstream_client = None


def get_eventstream_client(config: EventStreamConfig | None = None) -> EventStreamClient:
    global _eventstream_client
    if _eventstream_client is None:
        _eventstream_client = EventStreamClient(config=config)
    elif config:
        # if config changed, re-init producer
        if _eventstream_client.config != config:
            _eventstream_client.config = config
            with _eventstream_client._lock:
                _eventstream_client.producer = None
    return _eventstream_client


