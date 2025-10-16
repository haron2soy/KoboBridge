import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from flask import request
import hashlib
import hmac

from config import webhook_config
from validators import PayloadValidator
from eventstream_client import get_eventstream_client
from models import WebhookLog, db
print("Hey Hey here@webhook_handler:",WebhookLog.query.count())


logger = logging.getLogger(__name__)

class WebhookHandler:
    """Handles KoboToolbox webhook requests with validation and processing."""
    
    def __init__(self):
        self.validator = PayloadValidator()
    
    def process_webhook(self, request_data: Any) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Process incoming webhook request.
        
        Args:
            request_data: Flask request object
        
        Returns:
            Tuple of (success, message, response_data)
        """
        start_time = time.time()
        webhook_log = None
        
        try:
            # Create initial log entry
            webhook_log = WebhookLog()
            webhook_log.source_ip = request.remote_addr
            webhook_log.user_agent = request.headers.get('User-Agent', '')
            webhook_log.status = 'processing'
            db.session.add(webhook_log)
            db.session.flush()  # Get the ID without committing
            
            # Validate request
            is_valid, validation_errors = self._validate_request(request_data)
            if not is_valid:
                webhook_log.status = 'failed'
                webhook_log.error_message = '; '.join(validation_errors)
                db.session.commit()
                
                logger.warning(f"Webhook validation failed: {'; '.join(validation_errors)}")
                return False, f"Validation failed: {'; '.join(validation_errors)}", {}
            
            # Parse and validate payload
            payload = request_data.get_json()
            webhook_log.payload_size = len(json.dumps(payload, default=str))
            
            # Extract KoboToolbox metadata
            webhook_log.kobo_form_id = payload.get('_xform_id_string')
            webhook_log.submission_uuid = payload.get('_uuid')
            
            # Validate payload structure
            is_valid_payload, payload_errors = self.validator.validate_kobo_payload(payload)
            if not is_valid_payload:
                webhook_log.status = 'failed'
                webhook_log.error_message = '; '.join(payload_errors)
                db.session.commit()
                
                logger.warning(f"Payload validation failed: {'; '.join(payload_errors)}")
                return False, f"Payload validation failed: {'; '.join(payload_errors)}", {}
            
            # Sanitize payload
            sanitized_payload = self.validator.sanitize_payload(payload)
            
            # Send to EventStream
            '''try:
                success = eventstream_client.send_to_eventstream(
                    sanitized_payload, 
                    webhook_log.id
                )'''
            try:
                client = get_eventstream_client()
                success = client.send_to_eventstream(
                    sanitized_payload,
                    webhook_log.id
                )
                
                if success:
                    webhook_log.status = 'success'
                    webhook_log.eventstream_sent = True
                    processing_time = (time.time() - start_time) * 1000
                    webhook_log.processing_time_ms = processing_time
                    
                    logger.info(f"Webhook processed successfully in {processing_time:.2f}ms")
                    db.session.commit() 
                    
                    return True, "Webhook processed successfully", {
                        'webhook_id': webhook_log.id,
                        'processing_time_ms': processing_time,
                        'payload_size': webhook_log.payload_size
                    }
                else:
                    webhook_log.status = 'failed'
                    webhook_log.error_message = 'EventStream transmission failed'
                    
            except Exception as e:
                webhook_log.status = 'failed'
                webhook_log.error_message = str(e)
                logger.error(f"EventStream transmission failed: {str(e)}")
                return False, f"EventStream transmission failed: {str(e)}", {}
            
        except Exception as e:
            if webhook_log:
                webhook_log.status = 'failed'
                webhook_log.error_message = str(e)
            
            logger.error(f"Webhook processing failed: {str(e)}")
            return False, f"Processing failed: {str(e)}", {}
        
        finally:
            # Always save the log
            try:
                if webhook_log:
                    webhook_log.processing_time_ms = webhook_log.processing_time_ms or (time.time() - start_time) * 1000
                    db.session.commit()
            except Exception as db_error:
                logger.error(f"Failed to save webhook log: {str(db_error)}")
        
        return False, "Unknown error", {}
    
    def _validate_request(self, request_data: Any) -> Tuple[bool, list]:
        """Validate the incoming request."""
        errors = []
        
        # Check content type
        if not request_data.is_json:
            errors.append("Request must be JSON")
        
        # Check payload size
        content_length = request_data.content_length
        if content_length and content_length > webhook_config.max_payload_size:
            errors.append(f"Payload too large (max {webhook_config.max_payload_size} bytes)")
        
        # Verify webhook signature if configured
        if webhook_config.verify_signature and webhook_config.kobo_secret:
            if not self._verify_signature(request_data):
                errors.append("Invalid webhook signature")
        
        return len(errors) == 0, errors
    
    def _verify_signature(self, request_data: Any) -> bool:
        """Verify webhook signature from KoboToolbox."""
        if not webhook_config.kobo_secret:
            logger.warning("Webhook signature verification enabled but no secret configured")
            return False
        
        signature_header = request_data.headers.get('X-Kobo-Signature')
        if not signature_header:
            logger.warning("Missing X-Kobo-Signature header")
            return False
        
        try:
            # Get raw request data
            payload = request_data.get_data()
            
            # Calculate expected signature
            expected_signature = hmac.new(
                webhook_config.kobo_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(signature_header, expected_signature)
            
        except Exception as e:
            logger.error(f"Signature verification failed: {str(e)}")
            return False
    
    def get_recent_logs(self, limit: int = 10) -> list:
        """Get recent webhook logs."""
        try:
            logs = db.session.query(WebhookLog)\
                .order_by(WebhookLog.timestamp.desc())\
                .limit(limit)\
                .all()
            
            return [{
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'status': log.status,
                'kobo_form_id': log.kobo_form_id,
                'submission_uuid': log.submission_uuid,
                'processing_time_ms': log.processing_time_ms,
                'payload_size': log.payload_size,
                'error_message': log.error_message,
                'retry_count': log.retry_count
            } for log in logs]
            
        except Exception as e:
            logger.error(f"Failed to get recent logs: {str(e)}")
            return []

# Global webhook handler instance
webhook_handler = WebhookHandler()
