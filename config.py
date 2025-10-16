import os
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)

@dataclass
class EventStreamConfig:
    """Configuration for EventStream connection."""
    connection_string: str
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: int = 30
    
    @classmethod
    def from_db_or_session(cls, config_source) -> 'EventStreamConfig':

        #print("checkingsomething:", config_source)
        try:
            if config_source is None:
                raise ValueError("No EventStream configuration provided")

            if isinstance(config_source, dict):
                endpoint = config_source.get("endpoint")
                sharedaccesskeyname = config_source.get("sharedaccesskeyname")
                sharedaccesskey = config_source.get("sharedaccesskey")
                entitypath = config_source.get("entitypath")
                max_retries = int(config_source.get("max_retries", 3))
                retry_delay = float(config_source.get("retry_delay", 1.0))
                timeout = int(config_source.get("timeout", 30))

            else:  # Assume SQLAlchemy model
                endpoint = config_source.endpoint
                sharedaccesskeyname = config_source.sharedaccesskeyname
                sharedaccesskey = config_source.sharedaccesskey
                entitypath = config_source.entitypath
                max_retries = config_source.max_retries or 3
                retry_delay = config_source.retry_delay or 1.0
                timeout = config_source.timeout or 30

            if not all([endpoint, sharedaccesskeyname, sharedaccesskey, entitypath]):
                raise ValueError("Missing one or more required EventStream config fields msg@config")

            connection_string = (
                f"endpoint={endpoint}/;"
                f"sharedaccesskeyname={sharedaccesskeyname};"
                f"sharedaccesskey={sharedaccesskey};"
                f"entitypath={entitypath}"
            )

            return cls(
                connection_string=connection_string,
                max_retries=max_retries,
                retry_delay=retry_delay,
                timeout=timeout,
            )

        except Exception as e:
            logger.error(f"Failed to build EventStreamConfig: {e}")
            raise


@dataclass
class WebhookConfig:
    """Configuration for webhook handling."""
    verify_signature: bool = True
    kobo_secret: Optional[str] = None
    max_payload_size: int = 10 * 1024 * 1024  # 10MB

    @classmethod
    def from_env(cls) -> 'WebhookConfig':
        """Create configuration from environment variables."""
        return cls(
            verify_signature=os.getenv("WEBHOOK_VERIFY_SIGNATURE", "true").lower() == "true",
            kobo_secret=os.getenv("KOBO_WEBHOOK_SECRET"),
            max_payload_size=int(os.getenv("MAX_PAYLOAD_SIZE", str(10 * 1024 * 1024)))
        )

# Global configuration instances
#eventstream_config = EventStreamConfig.from_db_or_session()
webhook_config = WebhookConfig.from_env()



basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key")
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or "sqlite:///" + os.path.join(basedir, "instance", "flaskstream.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False