import requests
import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from config_service import config_service

logger = logging.getLogger(__name__)

class KoboToolboxClient:
    """Client for KoboToolbox API integration"""
    
    def __init__(self, config_service_instance):
        self.config_service = config_service_instance
        self.streaming_active = False
        self.streaming_thread = None
        self.last_sync_time = None
        
    def get_api_config(self) -> Dict[str, Any]:
        """Get KoboToolbox API configuration"""
        config = {}
        
        # Get configuration settings
        settings = self.config_service.get_all_settings()
        
        if 'kobo_server_url' in settings:
            config['server_url'] = settings['kobo_server_url']['value']
        if 'kobo_api_token' in settings:
            config['api_token'] = settings['kobo_api_token']['value']  
        if 'kobo_project_id' in settings:
            config['project_id'] = settings['kobo_project_id']['value']
        if 'kobo_polling_interval' in settings:
            config['polling_interval'] = int(settings['kobo_polling_interval']['value'])
        if 'kobo_batch_size' in settings:
            config['batch_size'] = int(settings['kobo_batch_size']['value'])
            
        return config
    '''
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to KoboToolbox API"""
        try:
            config = self.get_api_config()
            
            if not config.get('server_url') or not config.get('api_token'):
                return False, "Missing server URL or API token"
            
            headers = {
                'Authorization': f'Token {config["api_token"]}',
                'Content-Type': 'application/json'
            }
            
            # Test basic API access
            url = f"{config['server_url']}/api/v2/assets/"
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                return True, f"Connection successful. Found {count} projects."
            else:
                return False, f"API request failed: {response.status_code} - {response.text}"
                
        except Exception as e:
            logger.error(f"KoboToolbox connection test failed: {str(e)}")
            logger.debug(f"Config in test_connection: {config}")
            return False, f"Connection test failed: {str(e)}"
    '''

    def test_connection(self, server_url: str, api_token: str) -> Tuple[bool, str]:
        """Test connection to KoboToolbox API with provided credentials."""
        logger.info("Error EMERGECES")
        try:
            if not server_url or not api_token:
                return False, "Missing server URL or API token"

            headers = {
                'Authorization': f'Token {api_token}',
                'Content-Type': 'application/json'
            }

            url = f"{server_url}/api/v2/assets/"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                return True, f"Connection successful. Found {count} projects."
            else:
                return False, f"API request failed: {response.status_code} - {response.text}"

        except Exception as e:
            logger.error(f"KoboToolbox connection test failed: {str(e)}")
            return False, f"Connection test failed: {str(e)}"


    def get_projects(self) -> Tuple[bool, str, List[Dict]]:
        """Get list of available projects/forms"""
        try:
            config = self.get_api_config()
            
            if not config.get('server_url') or not config.get('api_token'):
                return False, "Missing server URL or API token", []
            
            headers = {
                'Authorization': f'Token {config["api_token"]}',
                'Content-Type': 'application/json'
            }
            
            url = f"{config['server_url']}/api/v2/assets/"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                projects = []
                
                for asset in data.get('results', []):
                    if asset.get('asset_type') == 'survey':  # Only include surveys/forms
                        projects.append({
                            'uid': asset['uid'],
                            'name': asset['name'],
                            'date_created': asset.get('date_created'),
                            'deployment_count': asset.get('deployment__submission_count', 0)
                        })
                
                return True, f"Found {len(projects)} projects", projects
            else:
                return False, f"Failed to fetch projects: {response.status_code}", []
                
        except Exception as e:
            logger.error(f"Failed to get KoboToolbox projects: {str(e)}")
            return False, f"Error fetching projects: {str(e)}", []
    
    def get_submissions(self, limit: int = 50, since: Optional[datetime] = None) -> Tuple[bool, str, List[Dict]]:
        """Get form submissions from KoboToolbox"""
        try:
            config = self.get_api_config()
            
            if not config.get('server_url') or not config.get('api_token') or not config.get('project_id'):
                return False, "Missing configuration", []
            
            headers = {
                'Authorization': f'Token {config["api_token"]}',
                'Content-Type': 'application/json'
            }
            
            # Build URL with parameters
            url = f"{config['server_url']}/api/v2/assets/{config['project_id']}/data/"
            params = {'limit': limit, 'format': 'json'}
            
            if since:
                # Filter submissions since a specific time
                params['query'] = f'{{"_submission_time": {{"$gte": "{since.isoformat()}"}}}}'
            
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                submissions = data.get('results', [])
                
                logger.info(f"Retrieved {len(submissions)} submissions from KoboToolbox")
                return True, f"Retrieved {len(submissions)} submissions", submissions
            else:
                return False, f"Failed to fetch submissions: {response.status_code}", []
                
        except Exception as e:
            logger.error(f"Failed to get KoboToolbox submissions: {str(e)}")
            return False, f"Error fetching submissions: {str(e)}", []
    
    def start_streaming(self, eventstream_client, webhook_handler) -> Tuple[bool, str]:
        """Start real-time streaming from KoboToolbox to EventStream"""
        if self.streaming_active:
            return False, "Streaming is already active"
        
        config = self.get_api_config()
        if not config.get('server_url') or not config.get('api_token') or not config.get('project_id'):
            return False, "Missing KoboToolbox configuration"
        
        self.streaming_active = True
        self.last_sync_time = datetime.utcnow()
        
        # Start streaming thread
        self.streaming_thread = threading.Thread(
            target=self._streaming_worker,
            args=(eventstream_client, webhook_handler, config),
            daemon=True
        )
        self.streaming_thread.start()
        
        logger.info("Started KoboToolbox real-time streaming")
        return True, "Real-time streaming started"
    
    def stop_streaming(self) -> Tuple[bool, str]:
        """Stop real-time streaming"""
        if not self.streaming_active:
            return False, "Streaming is not active"
        
        self.streaming_active = False
        
        if self.streaming_thread and self.streaming_thread.is_alive():
            self.streaming_thread.join(timeout=5)
        
        logger.info("Stopped KoboToolbox real-time streaming")
        return True, "Real-time streaming stopped"
    
    def get_streaming_status(self) -> Dict[str, Any]:
        """Get current streaming status"""
        return {
            'active': self.streaming_active,
            'last_sync': self.last_sync_time.isoformat() if self.last_sync_time else None,
            'thread_alive': self.streaming_thread.is_alive() if self.streaming_thread else False
        }
    
    def _streaming_worker(self, eventstream_client, webhook_handler, config):
        """Background worker for streaming data"""
        polling_interval = config.get('polling_interval', 30)
        batch_size = config.get('batch_size', 50)
        
        logger.info(f"Starting streaming worker (interval: {polling_interval}s, batch: {batch_size})")
        
        while self.streaming_active:
            try:
                # Get new submissions since last sync
                success, message, submissions = self.get_submissions(
                    limit=batch_size,
                    since=self.last_sync_time
                )
                
                if success and submissions:
                    # Process each submission
                    processed = 0
                    for submission in submissions:
                        if not self.streaming_active:
                            break
                        
                        # Transform submission to webhook format
                        webhook_data = self._transform_submission_to_webhook(submission)
                        
                        # Send directly to EventStream
                        try:
                            eventstream_success = eventstream_client.send_to_eventstream(webhook_data)
                            if eventstream_success:
                                processed += 1
                                logger.debug(f"Streamed submission {submission.get('_id', 'unknown')} to EventStream")
                        except Exception as e:
                            logger.error(f"Failed to stream submission to EventStream: {str(e)}")
                    
                    if processed > 0:
                        logger.info(f"Streamed {processed} new submissions to EventStream")
                
                # Update last sync time
                self.last_sync_time = datetime.utcnow()
                
                # Wait for next polling cycle
                time.sleep(polling_interval)
                
            except Exception as e:
                logger.error(f"Error in streaming worker: {str(e)}")
                time.sleep(min(polling_interval, 60))  # Wait at least 60s on error
        
        logger.info("Streaming worker stopped")
    
    def _transform_submission_to_webhook(self, submission: Dict) -> Dict:
        """Transform KoboToolbox submission to webhook format"""
        # Add metadata to match webhook format
        webhook_data = submission.copy()
        
        # Ensure required fields
        if '_submission_time' not in webhook_data:
            webhook_data['_submission_time'] = datetime.utcnow().isoformat()
        
        # Add source identifier
        webhook_data['_source'] = 'kobo_streaming'
        webhook_data['_streaming_timestamp'] = datetime.utcnow().isoformat()
        
        return webhook_data