import os
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
import base64
from flask import session
from models import AppConfiguration, db, UserEventStreamConfig
from flask_login import current_user
from config import EventStreamConfig, WebhookConfig

logger = logging.getLogger(__name__)

class ConfigurationService:
    """Service for managing application configuration with encryption."""
    
    def __init__(self):
        self._encryption_key = self._get_or_create_encryption_key()
        self._cipher = Fernet(self._encryption_key)
    
    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for sensitive data."""
        key_env = os.getenv('CONFIG_ENCRYPTION_KEY')
        if key_env:
            return key_env.encode()
        
        # Generate a new key and store it
        key = Fernet.generate_key()
        logger.info("Generated new encryption key for configuration")
        return key
    
    def set_setting(self, name: str, value: str, encrypted: bool = True) -> bool:
        """Store a configuration setting."""
        try:
            # Encrypt the value if required
            stored_value = value
            if encrypted and value:
                stored_value = self._cipher.encrypt(value.encode()).decode()
            
            # Check if setting exists
            setting = AppConfiguration.query.filter_by(setting_name=name).first()
            
            if setting:
                setting.setting_value = stored_value
                setting.encrypted = encrypted
            else:
                setting = AppConfiguration()
                setting.setting_name = name
                setting.setting_value = stored_value
                setting.encrypted = encrypted
                db.session.add(setting)
            
            db.session.commit()
            logger.info(f"Configuration setting '{name}' updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set configuration '{name}': {str(e)}")
            db.session.rollback()
            return False
    
    def get_setting(self, name: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a configuration setting."""
        try:
            setting = AppConfiguration.query.filter_by(setting_name=name).first()
            
            if not setting:
                return default
            
            if not setting.setting_value:
                return default
            
            # Decrypt if necessary
            if setting.encrypted:
                try:
                    return self._cipher.decrypt(setting.setting_value.encode()).decode()
                except Exception as e:
                    logger.error(f"Failed to decrypt setting '{name}': {str(e)}")
                    return default
            else:
                return setting.setting_value
                
        except Exception as e:
            logger.error(f"Failed to get configuration '{name}': {str(e)}")
            return default
    
    def delete_setting(self, name: str) -> bool:
        """Delete a configuration setting."""
        try:
            setting = AppConfiguration.query.filter_by(setting_name=name).first()
            if setting:
                db.session.delete(setting)
                db.session.commit()
                logger.info(f"Configuration setting '{name}' deleted")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete configuration '{name}': {str(e)}")
            db.session.rollback()
            return False
    
        
    def get_eventstream_config(self) -> EventStreamConfig | None:
        """Return EventStreamConfig from session or DB."""
        cfg = session.get("eventstream_config")
        
        if cfg:
            
            try:
                return EventStreamConfig.from_db_or_session(cfg)
            except Exception as e:
                logger.error(f"Invalid session EventStream config: {e}")

        # 2. Check DB for current_user
        print("Current user: ", current_user, "user id:", current_user.id)
        if current_user and not current_user.is_anonymous:
            

            user_cfg = UserEventStreamConfig.query.filter_by(user_id=current_user.id).first()
            logger.info(f"Checking DB endpoint 1")
            if user_cfg:
                logger.info(f"Checking DB endpoint 2", user_cfg)
                try:
                    logger.debug(
                    "Fetched UserEventStreamConfig from DB: "
                    f"endpoint={user_cfg.endpoint}, "
                    f"sharedaccesskeyname={user_cfg.shared_access_key_name}, "
                    f"sharedaccesskey={user_cfg.shared_access_key}, "
                    f"entitypath={user_cfg.entity_path}, "
                    f"max_retries={user_cfg.max_retries}, "
                    f"retry_delay={user_cfg.retry_delay}, "
                    f"timeout={user_cfg.timeout}"
                    # ⚠️ Do not log user_cfg.shared_accesskey unless debugging secrets is safe
                )
                    return EventStreamConfig.from_db_or_session({
                        "endpoint": user_cfg.endpoint,
                        "sharedaccesskeyname": user_cfg.shared_access_key_name,
                        "sharedaccesskey": user_cfg.shared_access_key,
                        "entitypath": user_cfg.entity_path,
                        "max_retries": user_cfg.max_retries,
                        "retry_delay": user_cfg.retry_delay,
                        "timeout": user_cfg.timeout,
                    })
                except Exception as e:
                    logger.error(f"Invalid DB EventStream config for user {current_user.id}: {e}")

        logger.warning("No EventStream configuration available yet GET EVENTSTREAM CONFIG")
        return None 
        


    def get_webhook_config(self) -> WebhookConfig:
        """Get webhook configuration with fallbacks."""
        verify_signature = self.get_setting('webhook_verify_signature', 'true').lower() == 'true'
        kobo_secret = self.get_setting('kobo_webhook_secret')
        max_payload_size = int(self.get_setting('webhook_max_payload_size', str(10 * 1024 * 1024)))
        
        return WebhookConfig(
            verify_signature=verify_signature,
            kobo_secret=kobo_secret,
            max_payload_size=max_payload_size
        )
    
    def update_eventstream_config(self, connection_string: str, max_retries: int = 3, 
                                 retry_delay: float = 1.0, timeout: int = 30) -> bool:
        """Update EventStream configuration."""
        success = True
        success &= self.set_setting('eventstream_connection_string', connection_string, encrypted=True)
        success &= self.set_setting('eventstream_max_retries', str(max_retries), encrypted=False)
        success &= self.set_setting('eventstream_retry_delay', str(retry_delay), encrypted=False)
        success &= self.set_setting('eventstream_timeout', str(timeout), encrypted=False)
        return success
    
    def update_webhook_config(self, verify_signature: bool = True, kobo_secret: str = None, 
                            max_payload_size: int = 10 * 1024 * 1024) -> bool:
        """Update webhook configuration."""
        success = True
        success &= self.set_setting('webhook_verify_signature', 'true' if verify_signature else 'false', encrypted=False)
        if kobo_secret:
            success &= self.set_setting('kobo_webhook_secret', kobo_secret, encrypted=True)
        success &= self.set_setting('webhook_max_payload_size', str(max_payload_size), encrypted=False)
        return success
    
    def get_all_settings(self) -> Dict[str, Any]:
        """Get all configuration settings (without sensitive values)."""
        try:
            settings = AppConfiguration.query.all()
            result = {}
            
            for setting in settings:
                if setting.encrypted:
                    # Don't expose encrypted values, just indicate they exist
                    result[setting.setting_name] = {'configured': bool(setting.setting_value), 'encrypted': True}
                else:
                    result[setting.setting_name] = {'value': setting.setting_value, 'encrypted': False}
            
            return result
        except Exception as e:
            logger.error(f"Failed to get all settings: {str(e)}")
            return {}
    

    def set_api_config(self, server_url: str, api_token: str) -> None:
        """Save user-provided KoboToolbox configuration in session."""
        session["server_url"] = server_url.strip() if server_url else None
        session["api_token"] = api_token.strip() if api_token else None

    def get_api_config(self) -> dict:
        """Retrieve KoboToolbox configuration from session."""
        base_url = session.get("server_url")
        
        api_token = session.get("api_token")
        project_id = session.get("projectID")
        user_id = session["eventstream_config"]["user_id"]
        print("GET_API_CONFIG@SESSION", "BASE URL:", base_url, "API TOKEN:", api_token, "sessionthings", dict(session))
        print("SESSION AT GET_API_CONFIG=", "user_id:", user_id)
        return {
            
            "server_url": f"{base_url}/api/v2",
            "api_token": api_token,
            "project_id" : session.get("projectID"),
            "user_id"  : user_id
        }

    def clear_api_config(self) -> None:
        """Clear configuration when stream stops or app closes."""
        session.pop("server_url", None)
        session.pop("api_token", None)
        session.pop("user_id", None)


    def update_api_config(self, base_url: str, api_token: str) -> bool:
        """Update API-based configuration."""
        success = True
        success &= self.set_setting('server_url', base_url, encrypted=False)
        success &= self.set_setting('api_token', api_token, encrypted=True)
        return success

# Global configuration service instance
config_service = ConfigurationService()