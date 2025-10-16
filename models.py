from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import JSON
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

class WebhookLog(db.Model):
    """Model to track webhook requests and their processing status."""
    __tablename__ = 'webhook_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    source_ip = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.String(500))
    payload_size = db.Column(db.Integer)
    kobo_form_id = db.Column(db.String(100))
    submission_uuid = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False)  # success, failed, retry
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    eventstream_sent = db.Column(db.Boolean, default=False)
    processing_time_ms = db.Column(db.Float)
    
    def __repr__(self):
        return f'<WebhookLog {self.id}: {self.status}>'

class SystemHealth(db.Model):
    """Model to track system health metrics."""
    __tablename__ = 'system_health'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_requests = db.Column(db.Integer, default=0)
    successful_requests = db.Column(db.Integer, default=0)
    failed_requests = db.Column(db.Integer, default=0)
    average_processing_time = db.Column(db.Float, default=0.0)
    eventstream_connection_status = db.Column(db.String(20), default='unknown')
    last_successful_transmission = db.Column(db.DateTime)


    # 🔹 New fields
    last_webhook_log_id = db.Column(db.Integer, nullable=True)
    last_payload_preview = db.Column(JSON, nullable=True)
    last_error_message = db.Column(db.Text, nullable=True)
    last_attempt_time = db.Column(db.DateTime, nullable=True)

    
    def __repr__(self):
        return f'<SystemHealth {self.timestamp}>'

class EventStreamMetrics(db.Model):
    """Model to track EventStream transmission metrics."""
    __tablename__ = 'eventstream_metrics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    webhook_log_id = db.Column(db.Integer, db.ForeignKey('webhook_logs.id'))
    attempt_number = db.Column(db.Integer, default=1)
    success = db.Column(db.Boolean, default=False)
    error_type = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    transmission_time_ms = db.Column(db.Float)
    payload_preview = db.Column(JSON)  # Store first few fields for debugging
    
    # Relationship
    webhook_log = db.relationship('WebhookLog', backref='eventstream_attempts')
    
    def __repr__(self):
        return f'<EventStreamMetrics {self.id}: {"success" if self.success else "failed"}>'

class AppConfiguration(db.Model):
    """Model to store application configuration settings."""
    __tablename__ = 'app_configuration'
    
    id = db.Column(db.Integer, primary_key=True)
    #user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    setting_name = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    encrypted = db.Column(db.Boolean, default=True)  # Whether the value is encrypted
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<AppConfiguration {self.setting_name}>'
    
class UserEventStreamConfig(db.Model):
    __tablename__ = "user_eventstream_config"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)

    endpoint = db.Column(db.String(255), nullable=False)
    shared_access_key_name = db.Column(db.String(255), nullable=False)
    shared_access_key = db.Column(db.String(255), nullable=False)  # 🔐 encrypt this in practice
    entity_path = db.Column(db.String(255), nullable=False)

    max_retries = db.Column(db.Integer, default=3)
    retry_delay = db.Column(db.Float, default=1.0)
    timeout = db.Column(db.Integer, default=30)

    user = db.relationship("User", back_populates="eventstream_config")

'''class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    eventstream_config = db.relationship("UserEventStreamConfig", uselist=False, back_populates="user")'''
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    eventstream_config = db.relationship("UserEventStreamConfig", uselist=False, back_populates="user")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)