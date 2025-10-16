import requests
import logging
import time
import json
import threading
from datetime import datetime,  timedelta
from typing import Dict, List, Optional, Any, Tuple
from models import WebhookLog, SystemHealth, EventStreamMetrics, db

from app import create_app
from config_service import config_service
logger = logging.getLogger(__name__)


class KoboToolboxClient:
    """Client for KoboToolbox API integration with streaming support"""

    def __init__(self, config_service_instance=config_service):
        self.config_service = config_service_instance
        self.streaming_active = False
        self.streaming_thread = None
        self.last_sync_time: Optional[datetime] = None

    # ------------------------
       # Configuration
    # ------------------------
    def get_api_config(self) -> Dict[str, Any]:
        """Get KoboToolbox API configuration."""
        api_cfg = self.config_service.get_api_config()
        logger.info('@GETAPIConfig mambo testing MAMBO')
        print("CHECKING URL AND APITOKEN: ", api_cfg)
        return {
            "user_id" : api_cfg.get("user_id"),
            "server_url": api_cfg.get("server_url"),
            "api_token": api_cfg.get("api_token"),
            "project_id": api_cfg.get("project_id"),
            "polling_interval": int(self.config_service.get_setting("kobo_polling_interval", "30")),
            "batch_size": int(self.config_service.get_setting("kobo_batch_size", "50")),
        }

    # ------------------------
    # Connection & Metadata
    # ------------------------
    def test_connection(self, server_url: str, api_token: str) -> Tuple[bool, str]:
        """Test connection to KoboToolbox API by listing assets."""
        try:
            #config = self.get_api_config()
            if not server_url or not api_token:
                return False, "Missing server URL or API token"

            headers = {"Authorization": f'Token {api_token}'}
            url = f"{server_url.rstrip('/')}/api/v2/assets/"
            params = {"format": "json"}
            response = requests.get(url, headers=headers, params=params, timeout=10)

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response content (first 200 chars): {response.text[:200]}")

            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return False, f"Expected JSON but got {content_type}. Check URL/token."

            try:
                data = response.json()
                count = data.get("count", 0)
                return True, f"Connection successful. Found {count} projects."

            except ValueError as e:
                return False, f"Failed to parse JSON: {str(e)}"
            
            '''
                if response.status_code == 200:
                    count = response.json().get("count", 0)
                    return True, f"Connection successful. Found {count} projects."
                else:
                    return False, f"API request failed: {response.status_code} - {response.text}"
            '''
            
        except Exception as e:
            logger.error(f"KoboToolbox connection test failed: {str(e)}")
            return False, f"Connection test failed: {str(e)}"

    def get_projects(self) -> List[Dict[str, Any]]:
        """Get list of projects/forms from KoboToolbox."""
        try:
            config = self.get_api_config()
            if not config.get("server_url") or not config.get("api_token"):
                return []

            headers = {
                "Authorization": f'Token {config["api_token"]}',
                "Accept": "application/json",
            }
            url = f"{config['server_url'].rstrip('/')}/assets/"
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                projects = []
                for asset in response.json().get("results", []):
                    if asset.get("asset_type") == "survey":
                        uid = asset.get("uid") or asset.get("url", "").rstrip("/").split("/")[-1]
                        projects.append(
                            {
                                "uid": uid,
                                "name": asset.get("name") or asset.get("title") or uid,
                                "date_created": asset.get("date_created"),
                                "deployment_count": asset.get("num_submissions", 0),
                            }
                        )
                return projects
            else:
                logger.error(f"Failed to fetch projects: {response.status_code} - {response.text}")
                return []

        except Exception as e:
            logger.error(f"Failed to get KoboToolbox projects: {str(e)}")
            return []


    # ------------------------
    # Submissions
    # ------------------------
    def get_submissions(
        self, limit: int = 50, since: Optional[datetime] = None
    ) -> Tuple[bool, str, List[Dict]]:
        """Retrieve submissions for configured project."""
        try:
            config = self.get_api_config()
            if not config["server_url"] or not config["api_token"] or not config["project_id"]:
                return False, "Missing configuration", []

            headers = {"Authorization": f'Token {config["api_token"]}'}
            url = f"{config['server_url'].rstrip('/')}/assets/{config['project_id']}/data/"
            
            if since is None:
                query = json.dumps({})
            else:
                since_iso = since.isoformat()
                query = json.dumps({"_submission_time": {"gte": since_iso}})
            
            params = {"limit": limit, "format": "json", "query": query}

            '''if since:
                params["query"] = f'{{"_submission_time": {{"$gte": "{since.isoformat()}"}}}}'
                '''
            response = requests.get(url, headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                submissions = response.json().get("results", [])
                logger.info(f"Retrieved {len(submissions)} submissions from KoboToolbox")
                return True, f"Retrieved {len(submissions)} submissions", submissions
            else:
                return False, f"Failed to fetch submissions: {response.status_code}", []

        except Exception as e:
            logger.error(f"Failed to get KoboToolbox submissions: {str(e)}")
            return False, f"Error fetching submissions: {str(e)}", []

    # ------------------------
    # Streaming
    # ------------------------
    def start_streaming(self, eventstream_client, webhook_handler=None) -> Tuple[bool, str]:
        """Start background thread to stream Kobo submissions into EventStream."""
        print("When STARTING EVENTSTREAM@koboclient start streaming")
        if self.streaming_active:
            return False, "Streaming is already active"

        config = self.get_api_config()
        
        server_url = (config.get("server_url") or "").strip()
        
        api_token = (config.get("api_token") or "").strip()
        
        print("BBIG url: ", server_url, "api :", api_token)
        if not server_url or not server_url.strip():
            return False, "Missing or invalid KoboToolbox server URL"
        if not api_token or not api_token.strip():
            return False, "Missing or invalid KoboToolbox API token"

        

        self.streaming_active = True
        self.last_sync_time = datetime.utcnow()

        self.streaming_thread = threading.Thread(
            target=self._streaming_worker,
            args=(eventstream_client, webhook_handler, config),
            daemon=True,
        )
        self.streaming_thread.start()

        logger.info("Started KoboToolbox real-time streaming")
        return True, "Real-time streaming started"

    def stop_streaming(self) -> Tuple[bool, str]:
        """Stop streaming thread."""
        if not self.streaming_active:
            return False, "Streaming is not active"

        self.streaming_active = False
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=5)

        logger.info("Stopped KoboToolbox real-time streaming")
        return True, "Real-time streaming stopped"

    def get_streaming_status(self) -> Dict[str, Any]:
        """Report streaming worker status."""
        return {
            "active": self.streaming_active,
            "last_sync": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "thread_alive": self.streaming_thread.is_alive() if self.streaming_thread else False,
        }

    
    def _streaming_worker(self, eventstream_client, webhook_handler, config: Dict[str, Any]):
        """Background loop: poll KoboToolbox and forward new submissions to EventStream."""
        app = create_app()  # or import the already initialized app

        with app.app_context():
            polling_interval = config.get("polling_interval", 30)
            batch_size = config.get("batch_size", 50)

            server_url = config.get("server_url")
            api_token = config.get("api_token")
            project_id = config.get("project_id")
            user_id = config.get("user_id")
            
            print("USER_ID1", dict(config))
            user_id = config["user_id"]
            print("USER_ID2", user_id)

            logger.info(f"Streaming worker started (interval={polling_interval}s, batch={batch_size})")
            first_run = True

            while self.streaming_active:
                try:
                    # ✅ build request directly with config (no Flask session)
                    url = f"{server_url.rstrip('/')}/assets/{project_id}/data/"
                    headers = {"Authorization": f"Token {api_token}"}

                    if first_run or not self.last_sync_time:
                        query = {}
                    else:
                        query = {"_submission_time": {"$gte": self.last_sync_time.isoformat()}}

                    params = {"format": "json", "limit": batch_size, "query": json.dumps(query)}

                    response = requests.get(url, headers=headers, params=params, timeout=30)

                    if response.status_code == 200:
                        submissions = response.json().get("results", [])
                    else:
                        logger.error(f"Failed to fetch submissions (status {response.status_code}): {response.text}")
                        submissions = []

                    if submissions:
                        processed = 0
                        for submission in submissions:
                            if not self.streaming_active:
                                break
                            webhook_data = self._transform_submission_to_webhook(submission)
                            start_time = time.time()
                            status = "success"
                            error_message = None

                            try:
                                if eventstream_client.send_to_eventstream(webhook_data):
                                    processed += 1
                            except Exception as e:
                                status = "failed"
                                logger.error(f"Failed to stream submission: {str(e)}")
                            
                            # 🔹 Log webhook activity
                            log = WebhookLog(

                                user_id = user_id,  # or current_user.id if available
                                source_ip="kobo_client",
                                user_agent="streaming_worker",
                                payload_size=len(json.dumps(webhook_data)),
                                kobo_form_id=submission.get("_xform_id_string"),
                                submission_uuid=submission.get("_uuid"),
                                status=status,
                                error_message=error_message,
                                retry_count=0,
                                eventstream_sent=(status == "success"),
                                #eventstream_sent='sent' if status == "success" else 'failed',
                                processing_time_ms=(time.time() - start_time) * 1000
                            )
                            db.session.add(log)
                            db.session.flush()  # so log.id is available

                            # 🔹 Log eventstream attempt
                            metrics = EventStreamMetrics(
                                user_id= user_id,
                                webhook_log=log,
                                attempt_number=1,
                                success=(status == "success"),
                                error_type=(type(error_message).__name__ if error_message else None),
                                error_message=error_message,
                                transmission_time_ms=(time.time() - start_time) * 1000,
                                payload_preview={k: webhook_data[k] for k in list(webhook_data)[:5]}
                            )
                            db.session.add(metrics)
                        # 🔹 Commit once per batch
                        db.session.commit()
                        if processed > 0:
                            logger.info(f"Streamed {processed} submissions to EventStream")
                    else:
                        logger.warning("No new submissions.")

                    self.last_sync_time = datetime.utcnow()
                    first_run = False
                    time.sleep(polling_interval)

                except Exception as e:
                    logger.error(f"Error in streaming worker: {str(e)}")
                    time.sleep(min(polling_interval, 60))

            logger.info("Streaming worker stopped")


    # ------------------------
    # Helpers
    # ------------------------
    def _transform_submission_to_webhook(self, submission: Dict) -> Dict:
        """Transform submission to webhook-compatible format with metadata."""
        data = submission.copy()
        if "_submission_time" not in data:
            data["_submission_time"] = datetime.utcnow().isoformat()

        data["_source"] = "kobo_streaming"
        data["_streaming_timestamp"] = datetime.utcnow().isoformat()
        return data


# Global client instance
kobo_client = KoboToolboxClient()
