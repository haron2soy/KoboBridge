import logging
from datetime import datetime, timedelta
from flask import request, jsonify, render_template, session,redirect, url_for
from sqlalchemy import func
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from webhook_handler import webhook_handler
from eventstream_client import EventStreamClient, get_eventstream_client
#from eventstream_client import EventStreamClient
from config_service import config_service
from models import WebhookLog, db, User, UserEventStreamConfig
from kobo_client import KoboToolboxClient
#from flask_login import current_user, login_required
from eventstream_client import get_eventstream_client
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

def register_routes(app):
    """Register all routes with the Flask application."""
        
    # Initialize KoboToolbox client
    kobo_client = KoboToolboxClient(config_service)
    
    @app.route("/")
    def home():
        """Home page with dashboard."""
        return render_template('dashboard.html')

    
    @app.route("/kobo-webhook", methods=["POST"])
    def kobo_webhook():
        """
        Main webhook endpoint for KoboToolbox submissions.
        Validates, processes, and forwards data to Power BI EventStream.
        """
        try:
            success, message, data = webhook_handler.process_webhook(request)
            
            if success:
                return jsonify({
                    "status": "success",
                    "message": message,
                    "data": data
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": message
                }), 400
                
        except Exception as e:
            logger.error(f"Webhook endpoint error: {str(e)}")
            return jsonify({
                "status": "error",
                "message": "Internal server error"
            }), 500
    
    @app.route("/register", methods=["POST"])
    def register():
        logger.info("Register route called")
        print("Register route called")
        data = request.get_json()
        if not data or "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password required"}), 400

        # 1. Check if user exists
        existing_user = User.query.filter_by(username=data["username"]).first()
        if existing_user:
            print("Username already exists in DB.")
            return jsonify({"error": "Username already exists"}), 400

        # 2. Create new user (only once!)
        hashed_password = generate_password_hash(data["password"])
        new_user = User(username=data["username"], password_hash=hashed_password)

        try:
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify({"error": "Username already exists (IntegrityError caught)"}), 400

        # 3. Debug: print DB contents
        users = User.query.all()
        for u in users:
            print(f"User: {u.id}, {u.username}, {u.password_hash}")

        # 4. Debug: print session contents
        print("Session new:", db.session.new)     # new objects not yet committed
        print("Session dirty:", db.session.dirty) # modified objects
        print("Session deleted:", db.session.deleted)

        return jsonify({"message": "User registered successfully"}), 201
    

    @app.route("/login", methods=["POST"])
    def login():
        print("Hey Hey here@routes:",WebhookLog.query.count())
        
        
        data = request.get_json()
        if not data or "username" not in data or "password" not in data:
            return jsonify({"error": "Username and password required"}), 400

        user = User.query.filter_by(username=data["username"]).first()
        if user and check_password_hash(user.password_hash, data["password"]):
            login_user(user)

        
            has_cfg = bool(user.eventstream_config)
            logger.info("Login: user=%s has_eventstream_config=%s", user.username, has_cfg)
           
            # Preload EventStream config into session
            if has_cfg:
            
                session["eventstream_config"] = {
                    "endpoint": user.eventstream_config.endpoint,
                    "sharedaccesskeyname": user.eventstream_config.shared_access_key_name,
                    "sharedaccesskey": user.eventstream_config.shared_access_key,
                    "entitypath": user.eventstream_config.entity_path,
                    "max_retries": user.eventstream_config.max_retries,
                    "retry_delay": user.eventstream_config.retry_delay,
                    "timeout": user.eventstream_config.timeout,
                    "user_id": user.eventstream_config.user_id,
                }
            

            # Inspect session safely (don’t print secrets)
            safe_session = dict(session)
            if "eventstream_config" in safe_session:
                safe_session["eventstream_config"] = {
                    **safe_session["eventstream_config"],
                    "sharedaccesskey": "***",
                }
            print("Current Flask session (safe):")
           
            #print("Current Flask session:", dict(session))     # new objects not yet committed
           


            return jsonify({"message": "Logged in successfully"})
        else:
            logger.info("Invalid username or password")
            return jsonify({"error": "Invalid username or password"}), 401
    


    
    @app.route("/api/current-user")
    def current_user_api():
        if current_user.is_authenticated:
            session["user_id"]= current_user.id

            return jsonify({
                "authenticated": True,
                "username": current_user.username})
        else:
            return jsonify({
                "authenticated": False,
                "error": "Not yet logged in", "authenticated": False
            }), 200
   

        # If GET, return a simple message or JSON
        #return jsonify({"message": "Please log in with POST"})
    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        session.pop("eventstream_config", None)
        session.clear()
        #logout_user()
        kobo_client.stop_streaming()
        # ✅ Shut down EventStream producer to stop retries
        eventstream_client = get_eventstream_client()
        eventstream_client.shutdown()
        logger.info("@ /logout. REAL-TIME STREAMING STOPPED")
        print("Successfully logged out!")
        return jsonify({"message": "Logged out"})

    @app.route("/health", methods=["GET"])
    @login_required
    def health_check():
        """System health check endpoint."""
        try:
            # Get EventStream health
            
            #eventstream_health = eventstream_client.health_check()
            client = get_eventstream_client()
            eventstream_health = client.health_check()
            # Get database stats
            total_webhooks = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .count()
            successful_webhooks = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.status == 'success')\
                .count()
            
            # Calculate success rate
            success_rate = (successful_webhooks / total_webhooks * 100) if total_webhooks > 0 else 0
            
            # Get recent errors

            recent_errors = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.status == 'failed')\
                .filter(WebhookLog.timestamp >= datetime.utcnow() - timedelta(hours=24))\
                .count()
            
            health_status = {
                "status": "healthy" if eventstream_health['status'] == 'healthy' and recent_errors < 10 else "degraded",
                "timestamp": datetime.utcnow().isoformat(),
                "database": {
                    "total_webhooks": total_webhooks,
                    "successful_webhooks": successful_webhooks,
                    "success_rate_percent": round(success_rate, 2),
                    "recent_errors_24h": recent_errors
                },
                "eventstream": eventstream_health
            }
            
            return jsonify(health_status), 200
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }), 500
    
    @app.route("/api/stats", methods=["GET"])
    @login_required
    def get_stats():
        """Get system statistics for the dashboard."""
        try:
            # Get basic stats
            #total_webhooks = db.session.query(WebhookLog).count()
            total_webhooks = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .count()
            successful_webhooks = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.status == 'success')\
                .count()
            #successful_webhooks = db.session.query(WebhookLog)\
            #    .filter(WebhookLog.status == 'success').count()
            
            # Get today's stats
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            today_webhooks = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.timestamp >= today_start).count()
            today_successful = db.session.query(WebhookLog)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.timestamp >= today_start)\
                .filter(WebhookLog.status == 'success').count()
            
            # Get recent processing times
            recent_times = db.session.query(WebhookLog.processing_time_ms)\
                .filter(WebhookLog.user_id == current_user.id)\
                .filter(WebhookLog.processing_time_ms.isnot(None))\
                .filter(WebhookLog.timestamp >= datetime.utcnow() - timedelta(hours=1))\
                .all()
            
            avg_processing_time = sum(t[0] for t in recent_times) / len(recent_times) if recent_times else 0
            
            # Get EventStream metrics
            #eventstream_metrics = eventstream_client.get_metrics_summary()
            client = get_eventstream_client()
            eventstream_metrics = client.get_metrics_summary()
            stats = {
                "total_webhooks": total_webhooks,
                "successful_webhooks": successful_webhooks,
                "success_rate": round((successful_webhooks / total_webhooks * 100) if total_webhooks > 0 else 0, 2),
                "today_webhooks": today_webhooks,
                "today_successful": today_successful,
                "today_success_rate": round((today_successful / today_webhooks * 100) if today_webhooks > 0 else 0, 2),
                "average_processing_time_ms": round(avg_processing_time, 2),
                "eventstream_metrics": eventstream_metrics,
                "last_updated": datetime.utcnow().isoformat()
            }
            
            return jsonify(stats), 200
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/recent-logs", methods=["GET"])
    @login_required
    def get_recent_logs():
        """Get recent webhook logs."""
        try:
            limit = request.args.get('limit', 10, type=int)
            logs = (db.session.query(WebhookLog)
                .filter_by(user_id=current_user.id)
                .order_by(WebhookLog.timestamp.desc())
                .limit(limit)
                .all())
            return jsonify([log.to_dict() for log in logs]), 200
            
            #logs = webhook_handler.get_recent_logs(limit)
            #return jsonify(logs), 200
            
        except Exception as e:
            logger.error(f"Failed to get recent logs: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    
    @app.route("/api/latest-data", methods=["GET"])
    @login_required
    def get_latest_data():
        """Get latest data sent to EventStream."""
        try:
            # Get the last 10 webhook logs with EventStream data
            logs = webhook_handler.get_recent_logs(10)
            logs = (
            WebhookLog.query
            .filter_by(user_id=current_user.id)
            .order_by(WebhookLog.timestamp.desc())
            .limit(10)
            .all()
        )
            # Filter for successful EventStream transmissions
            latest_data = []
            #print("1something is sent to POWERBI", logs)
            for log in logs:
                if log.status == "success":
                    #print("2something is senting to POWERBI", log)
                    latest_data.append({
                        'timestamp': log.timestamp,
                        'status': 'success' if log.status == 'success' else 'failed',
                        'payload_size': getattr(log, 'payload_size', 0),
                        'processing_time': getattr(log, 'processing_time_ms', 0)
                    })
                    
            #print("3something is senting to POWERBI", latest_data)
            
            return jsonify(latest_data[:5]), 200  # Return only the latest 5
            
        except Exception as e:
            logger.error(f"Failed to get latest data: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({"error": "Endpoint not found"}), 404
    
    @app.route("/api/configuration", methods=["GET"])
    def get_configuration():
        """Get current configuration settings (non-sensitive)."""
        try:
            settings = config_service.get_all_settings()
            return jsonify({
                "settings": settings,
                "webhook_url": f"{request.host_url}kobo-webhook"
            }), 200
        except Exception as e:
            logger.error(f"Failed to get configuration: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/configuration/eventstream", methods=["POST"])
    @login_required
    def update_eventstream_config():
        data = request.get_json() or {}
        data = {k.lower(): v for k, v in data.items()}  # normalize keys

        logger.info("data in api/configuration/eventstream", data)
        required = ["endpoint", "sharedaccesskeyname", "sharedaccesskey", "entitypath"]
        if not all(k in data and data[k] for k in required):
            return jsonify({"error": "Missing one or more required fields"}), 400

        # always update session (mask key in logs)
        session["eventstream_config"] = {
            "endpoint": data["endpoint"],
            "entitypath": data["entitypath"],
            "sharedaccesskeyname": data["sharedaccesskeyname"],
            "sharedaccesskey": data["sharedaccesskey"],
            "max_retries": int(data.get("max_retries", 3)),
            "retry_delay": float(data.get("retry_delay", 1.0)),
            "timeout": int(data.get("timeout", 30)),
        }

        if data.get("save_to_db"):
            try: 
                cfg = UserEventStreamConfig.query.filter_by(user_id=current_user.id).first()

                if cfg:
                    # Check if identical
                    same = (
                        cfg.endpoint == data["endpoint"]
                        and cfg.entity_path == data["entitypath"]
                        and cfg.shared_access_key_name == data["sharedaccesskeyname"]
                        and cfg.shared_access_key == data["sharedaccesskey"]
                        and cfg.max_retries == int(data.get("max_retries", 3))
                        and cfg.retry_delay == float(data.get("retry_delay", 1.0))
                        and cfg.timeout == int(data.get("timeout", 30))
                    )

                    if same:
                        print(f"[INFO] user_id={current_user.id} config exists, identical — skipping DB write")
                    else:
                        print(f"[INFO] user_id={current_user.id} config exists but different — updating DB")
                        cfg.endpoint = data["endpoint"]
                        cfg.entity_path = data["entitypath"]
                        cfg.shared_access_key_name = data["sharedaccesskeyname"]
                        cfg.shared_access_key = data["sharedaccesskey"]
                        cfg.max_retries = int(data.get("max_retries", 3))
                        cfg.retry_delay = float(data.get("retry_delay", 1.0))
                        cfg.timeout = int(data.get("timeout", 30))
                        db.session.commit()

                else:
                    print(f"[INFO] user_id={current_user.id} has no config — creating new")
                    cfg = UserEventStreamConfig(
                        user_id=current_user.id,
                        endpoint=data["endpoint"],
                        entity_path=data["entitypath"],
                        shared_access_key_name=data["sharedaccesskeyname"],
                        shared_access_key=data["sharedaccesskey"],
                        max_retries=int(data.get("max_retries", 3)),
                        retry_delay=float(data.get("retry_delay", 1.0)),
                        timeout=int(data.get("timeout", 30)),
                    )
                    db.session.add(cfg)
                    db.session.commit()
             
            except IntegrityError:
                db.session.rollback()
                print(f"[WARN] user_id={current_user.id} duplicate insert attempt — fetching existing")
                cfg = UserEventStreamConfig.query.filter_by(user_id=current_user.id).first()
        
        return jsonify({"status": "success", "message": "EventStream config updated"}), 200

    
    @app.route("/eventstream-config", methods=["POST"])
    @login_required
    def save_eventstream_config():
        data = request.get_json()

        # Save to session always
        session["eventstream_config"] = data
             

        return jsonify({"message": "EventStream config saved"})

        
    @app.route("/api/configuration/webhook", methods=["POST"])
    @login_required
    def update_webhook_config():
        """Update webhook configuration."""
        try:
            data = request.get_json()
            
            verify_signature = data.get('verify_signature', True)
            kobo_secret = data.get('kobo_secret', '')
            max_payload_size = data.get('max_payload_size', 10 * 1024 * 1024)
            
            success = config_service.update_webhook_config(
                verify_signature, kobo_secret, max_payload_size
            )
            
            if success:
                return jsonify({"status": "success", "message": "Webhook configuration updated"}), 200
            else:
                return jsonify({"error": "Failed to save configuration"}), 500
                
        except Exception as e:
            logger.error(f"Failed to update webhook config: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    @app.route("/api/test-eventstream", methods=["POST"])
    @login_required
    def test_eventstream_with_config():
        """Test EventStream connection with current configuration."""
        try:
            # Get current config and test
            eventstream_config = config_service.get_eventstream_config()
            #if eventstream_config:
              #  print("printing eventstream_config: ", eventstream_config)
           
            if not eventstream_config:
                #logger.error("No EventStream configuration found for current user/session")
                return jsonify({
                    "status": "error",
                    "message": "No EventStream configuration available. Please configure before testing."
                }), 401
                
            
            test_payload = {
                "_id": f"config_test_{datetime.utcnow().isoformat()}",
                "_submission_time": datetime.utcnow().isoformat(),
                "_submitted_by": "configuration_test",
                "test_message": "Configuration test from FlaskStream",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            #success = eventstream_client.send_to_eventstream(test_payload)
            client = get_eventstream_client(config=eventstream_config)
            # Create client from this config
            
            #client = EventStreamClient(eventstream_config)
            print("@routes eventstream_config: ", eventstream_config)
            success = client.send_to_eventstream(test_payload) 
            if success:
                return jsonify({
                    "status": "success",
                    "message": "EventStream test successful with current configuration",
                    "payload": test_payload
                }), 200
            else:
                return jsonify({
                    "status": "error",
                    "message": "EventStream test failed"
                }), 500
                
        except Exception as e:
            logger.error(f"EventStream configuration test failed: {str(e)}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors."""
        return jsonify({"error": "Endpoint not found"}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors."""
        logger.error(f"Internal server error: {str(error)}")
        return jsonify({"error": "Internal server error"}), 500
    
    
    
    # --- KoboToolbox API Config Routes ---
    @app.route("/api/configuration/kobo", methods=["POST"])
    def update_kobo_config():
        """Save KoboToolbox API configuration."""
        try:
            data = request.get_json()
            print("@ROUTE.PY Configuration KOBO", data)

            server_url = data.get("server_url")
            api_token = data.get("api_token")

            if not server_url or not api_token:
                return jsonify({"error": "Base URL and API token required"}), 400

            #success = config_service.update_api_config(server_url, api_token)
            config_service.set_api_config(server_url, api_token)
           
            return jsonify({"status": "success", "message": "KoboToolbox config saved"}), 200
            
        except Exception as e:
            logger.error(f"Failed to update Kobo config: {str(e)}")
            return jsonify({"error": str(e)}), 500


    
    @app.route("/api/kobo/test-connection", methods=["POST"])
    def test_kobo_connection():
        """Test connection to KoboToolbox API with provided credentials."""
        try:
            data = request.get_json()
            server_url = data.get("server_url")
            api_token = data.get("api_token")

            print("Received JSON:", data)  # <-- log the full payload
            logger.info(f"Received JSON: {data}")  # optional: logs in your log file

            print("server_url:", server_url, "api_token:", api_token)
            logger.info(f"server_url: {server_url}, api_token: {api_token}")


            if not server_url or not api_token:
                return jsonify({"status": "error", "message": "Missing server URL or API token"}), 400

            success, message = kobo_client.test_connection(server_url, api_token)
            return jsonify({
                "status": "success" if success else "error",
                "message": message
            }), 200 if success else 400
        except Exception as e:
            logger.error(f"Kobo connection test failed: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route("/api/kobo/projects", methods=["POST"])
    def list_kobo_projects():
        """List projects from KoboToolbox API."""
        try:
            data = request.json
            session['server_url'] = data.get('server_url')
            session['api_token'] = data.get('api_token')
            projects = kobo_client.get_projects()
            return jsonify({"projects": projects}), 200
        except Exception as e:
            logger.error(f"Failed to fetch projects: {str(e)}")
            return jsonify({"error": str(e)}), 500
        

    @app.route("/api/streaming/status", methods=["GET"])
    def streaming_status():
        # Example: you can maintain a variable in memory, Redis, or DB
        return jsonify({
            "status": "stopped or not sure!",   # or "running"
            "last_checked": datetime.utcnow().isoformat()
        })
    @app.route("/api/kobo/start", methods=["POST"])
    def start_kobo_streaming():
        """Start KoboToolbox real-time streaming."""
        try:
            data = request.get_json()
            #api_token = data.get("api_token")
            project_id = data.get("project_id")
            if project_id:
                session["projectID"] = project_id

            
            
            # ✅ snapshot config inside request context
            eventstream_config = config_service.get_eventstream_config()
            
            print("evenstream_config@routes", eventstream_config)

            if not eventstream_config:
                return jsonify({"status": "error", "message": "No EventStream config available"}), 400
            #success, message = kobo_client.start_streaming(eventstream_client)
            
            #client = get_eventstream_client()
            #success, message = client.send_to_eventstream(client)
            
            
            #client = get_eventstream_client(eventstream_config)
            client = EventStreamClient(config=eventstream_config)
            #client = eventstream_client(config=eventstream_config)
            success, message = kobo_client.start_streaming(client)


            if success:
                return jsonify({"status": "success", "message": message}), 200
            else:
                return jsonify({"status": "error", "message": message}), 400
        except Exception as e:
            logger.error(f"Failed to start streaming: {str(e)}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/kobo/stop", methods=["POST"])
    def stop_kobo_streaming():
        """Stop KoboToolbox real-time streaming."""
        try:
            kobo_client.stop_streaming()
            # ✅ Shut down EventStream producer to stop retries
            eventstream_client = get_eventstream_client()
            eventstream_client.close()
            logger.log("INFO, successfully called kobo/stop. REAL-TIME STREAMING STOPPED")
            return jsonify({"status": "success", "message": "Streaming stopped"}), 200
        except Exception as e:
            logger.error(f"Failed to stop streaming: {str(e)}")
            return jsonify({"error": str(e)}), 500

