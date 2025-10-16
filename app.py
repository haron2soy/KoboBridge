import os
import logging
from flask import Flask, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db   # <-- import from extensions, not here
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # or WARNING
from flask_login import LoginManager
from models import User
from flask_migrate import Migrate


log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)  # or WARNING

login_manager = LoginManager()
login_manager.login_view = "login"  # redirect if not logged in

def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.config.from_object("config.Config")

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("flaskstream.log"),
        ],
    )

    # Proxy handling
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Database config
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///flaskstream.db")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize db
    db.init_app(app)
    Migrate(app, db)

    # Initialize Flask-Login
    login_manager.init_app(app)

    @login_manager.unauthorized_handler
    def unauthorized_callback():
        return jsonify({"authenticated": False, "error": "Login required"}), 401

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        from models import WebhookLog, SystemHealth, EventStreamMetrics
        from routes import register_routes
        register_routes(app)

    return app


# Application instance
app = create_app()

'''def create_app():
    app = Flask(__name__)
    app.secret_key = "super-secret-key"
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('flaskstream.log')
        ]
    )
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Database config
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///flaskstream.db")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    
    # Initialize db
    db.init_app(app)
    
    with app.app_context():
        from models import WebhookLog, SystemHealth, EventStreamMetrics  # safe now
        db.create_all()
        
        from routes import register_routes
        register_routes(app)
    

    return app

# Application instance
app = create_app()'''
