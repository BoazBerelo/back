from flask import Flask, request, jsonify, redirect 
from flask_cors import CORS
from login import check_login, check_username_avaliability, registration
from domains_check_MT import check_url_mt as check_url
from DataManagement import (load_domains, remove_domain, update_user_task, delete_user_task, load_user_tasks)
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from config import Config, logger
import requests
from oauthlib.oauth2 import WebApplicationClient
import json
import time
from utils import Utils
from elasticapm.contrib.flask import ElasticAPM
from elasticapm import set_custom_context, capture_span, traces
import elasticapm


utils = Utils()

# Initialize Flask application
app = Flask(__name__)

# Initialize Elastic APM

apm_client= elasticapm.Client(service_name='BackendService_Ilya',  
                            server_url=(Config.SERVER_URL),
                            secret_token=(Config.SECRET_TOKEN),
                            environment='dev',
                            debug=True
)


# Enable CORS for all routes
CORS(app, resources={
    r"/api/*": {
        "origins": Config.CORS_ALLOWED_ORIGINS,
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

os.environ['OAUTHLIB_INSECURE_TRANSPORT']='1'

# Initialize scheduler for background tasks
scheduler = BackgroundScheduler()
scheduler.start()

# Google OAuth client setup
client = WebApplicationClient(Config.GOOGLE_CLIENT_ID)

# Authentication routes
@app.route("/api/auth/login", methods=['POST', 'GET'])
def login():
    """Handle user login"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if check_login(username, password):
        logger.info(f"Successful login for user: {username}")
        return jsonify({"status": "success"})
    
    logger.warning(f"Failed login attempt for user: {username}")
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401

@app.route("/api/auth/check-username", methods=['GET'])
def check_username():
    """Check if username is available"""
    username = request.args.get('username')
    try:
        is_available = check_username_avaliability(username)
        return jsonify({"available": is_available})
    except Exception as e:
        logger.error(f"Error checking username availability: {str(e)}")
        return jsonify({"error": "Server error"}), 500

@app.route("/api/auth/register", methods=['POST'])
def register_user():
    """Handle user registration"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    try:
        if not check_username_avaliability(username):
            return jsonify({"status": "error", "message": "Username already taken"}), 400
        
        registration(username, password)
        logger.info(f"New user registered: {username}")
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Google OAuth routes
@app.route("/google-login")
def google_login():
    """Initiate Google OAuth process"""
    google_provider_cfg = requests.get(Config.GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    
    callback_url = Config.CallbackUrl  # This should point to your frontend callback URL
    
    request_uri = client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=callback_url,
        scope=["openid", "email", "profile"]
    )
    return redirect(request_uri)

@app.route("/google-login/callback")
def google_callback():
    """Handle the OAuth callback and return user data"""
    try:
        code = request.args.get("code")
        google_provider_cfg = requests.get(Config.GOOGLE_DISCOVERY_URL).json()
        token_endpoint = google_provider_cfg["token_endpoint"]

        # Get tokens
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=Config.CallbackUrl,
            code=code
        )
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(Config.GOOGLE_CLIENT_ID, Config.GOOGLE_CLIENT_SECRET),
        )

        client.parse_request_body_response(json.dumps(token_response.json()))
        
        # Get user info
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)

        if userinfo_response.json().get("email_verified"):
            user_data = userinfo_response.json()
            unique_id = user_data["sub"]
            user_email = user_data["email"]
            user_name = user_data.get("name", "")
            
            # Register if new user
            if check_username_avaliability(user_email):
                registration(
                    username=user_email,
                    password=unique_id,
                    full_name=user_name,
                    is_google_user=True
                )
            
            return jsonify({
                "email": user_email,
                "name": user_name,
                "picture": user_data.get("picture")
            })
            
        return jsonify({"error": "Email not verified"}), 400
        
    except Exception as e:
        logger.error(f"Error in Google callback: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Domain management routes
@app.route("/api/domains/check", methods=['POST'])
@utils.measure_this
def check_domains():
    apm_client.begin_transaction('domain_check')
    apm_context=traces.execution_context.get_transaction()
    """Check status of provided domains"""
    try:
        data = request.json
        domains = data.get('domains', [])
        username = data.get('username')
        logger.info(f"User {username} started checking {len(domains)} domains.")
        

        if not domains or not username:
            return jsonify({"error": "Missing required data"}), 400
        
        results = check_url(domains, username , apm_context)

        #logger.info(f"Results: {results}")
        apm_client.end_transaction('domain_check' , 'success')
        return jsonify(results)
    except Exception as e:
        logger.error(f"Domain check error: {str(e)}")
        apm_client.end_transaction('domain_check' , 'failed')
        return jsonify({"error": str(e)}), 500

@app.route("/api/domains/list", methods=['GET'])
@utils.measure_this
def get_domains():
    """Get list of domains for a user"""
    try:
        username = request.args.get('username')
        if not username:
            return jsonify({"error": "Username required"}), 400
            
        domains = load_domains(username)
        return jsonify(domains)
    except Exception as e:
        logger.error(f"Error loading domains: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/domains/remove", methods=['DELETE'])
def remove_domain_endpoint():
    """Remove a domain for a user"""
    try:
        username = request.args.get('username')
        domain = request.args.get('domain')
        
        if not domain or not username:
            return jsonify({"error": "Missing required parameters"}), 400
            
        if remove_domain(domain, username):
            logger.info(f"Domain removed: {domain} for user: {username}")
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Domain not found"}), 404
    except Exception as e:
        logger.error(f"Error removing domain: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Scheduler routes

scheduler = BackgroundScheduler({
    'apscheduler.timezone': 'UTC',
    'apscheduler.job_defaults.coalesce': True,  # Combine missed executions
    'apscheduler.job_defaults.max_instances': 1  # Prevent multiple instances
})
scheduler.start()

@app.route("/api/schedule/hourly", methods=["POST"])
def schedule_hourly():
    """Set up hourly domain checking with proper state management"""
    try:
        data = request.json
        username = data.get('username')
        interval = data.get('interval', 1)
        
        # Get the domains for this user
        domains = [domain["url"] for domain in load_domains(username)]
        
        if not domains:
            return jsonify({"status": "error", "message": "No domains found"}), 400

        def scheduled_task():
            """Wrapper function to handle the scheduled check and update next run time"""
            try:
                logger.info(f"Starting scheduled check for user {username}")
                # Perform the domain check
                check_url(domains, username)
                
                # Get the current job and its next run time
                job = scheduler.get_job(f"{username}_hourly_task")
                if job and job.next_run_time:
                    # Update the task information in our database
                    new_task = {
                        "type": "hourly",
                        "interval": interval,
                        "next_run": job.next_run_time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "job_id": f"{username}_hourly_task",
                        "last_run": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    }
                    update_user_task(username, new_task)
                    logger.info(f"Updated next run time for {username} to {job.next_run_time}")
            except Exception as e:
                logger.error(f"Error in scheduled task for {username}: {str(e)}")

        # Remove any existing job for this user
        job_id = f"{username}_hourly_task"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # Add the new job with the wrapper function
        job = scheduler.add_job(
            func=scheduled_task,
            trigger=IntervalTrigger(
                hours=interval,
                start_date=datetime.now() + timedelta(seconds=5)  # Start in 5 seconds
            ),
            id=job_id,
            name=f"Hourly domain check for {username}",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )

        # Record the initial task information
        next_run = job.next_run_time
        new_task = {
            "type": "hourly",
            "interval": interval,
            "next_run": next_run.strftime("%Y-%m-%dT%H:%M:%S"),
            "job_id": job_id,
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        update_user_task(username, new_task)

        return jsonify({
            "status": "success",
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Hourly schedule created successfully"
        })

    except Exception as e:
        logger.error(f"Error setting up hourly schedule: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/schedule/daily", methods=["POST"])
def schedule_daily():
    """Set up daily domain checking with proper state management"""
    try:
        data = request.json
        username = data.get('username')
        time = data.get('time', '00:00')
        hour, minute = map(int, time.split(':'))
        
        # Get the domains for this user
        domains = [domain["url"] for domain in load_domains(username)]
        
        if not domains:
            return jsonify({"status": "error", "message": "No domains found"}), 400

        def scheduled_daily_task():
            """Wrapper function to handle the daily check and update next run time"""
            try:
                logger.info(f"Starting scheduled daily check for user {username}")
                
                # Perform the domain check
                check_url(domains, username)
                
                # Get the current job and its next run time
                job = scheduler.get_job(f"{username}_daily_task")
                if job and job.next_run_time:
                    # Update the task information in our database
                    new_task = {
                        "type": "daily",
                        "time": time,
                        "next_run": job.next_run_time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "job_id": f"{username}_daily_task",
                        "last_run": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    }
                    update_user_task(username, new_task)
                    logger.info(f"Updated next run time for {username}'s daily task to {job.next_run_time}")
            except Exception as e:
                logger.error(f"Error in daily scheduled task for {username}: {str(e)}")

        # Remove any existing job for this user
        job_id = f"{username}_daily_task"
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        # Calculate the first run time
        now = datetime.now()
        run_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the specified time has already passed today, start tomorrow
        if run_time <= now:
            run_time = run_time + timedelta(days=1)

        # Add the new job with the wrapper function
        job = scheduler.add_job(
            func=scheduled_daily_task,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                start_date=run_time  # Ensure first run is at the correct time
            ),
            id=job_id,
            name=f"Daily domain check for {username} at {time}",
            replace_existing=True,
            coalesce=True,
            max_instances=1
        )

        # Record the initial task information
        next_run = job.next_run_time
        new_task = {
            "type": "daily",
            "time": time,
            "next_run": next_run.strftime("%Y-%m-%dT%H:%M:%S"),
            "job_id": job_id,
            "created_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        }
        update_user_task(username, new_task)

        return jsonify({
            "status": "success",
            "next_run": next_run.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Daily schedule created successfully"
        })

    except Exception as e:
        logger.error(f"Error setting up daily schedule: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/schedule/stop", methods=["POST"])
def stop_schedule():
    """Stop scheduled tasks for a user"""
    try:
        username = request.json.get('username')
        if not username:
            return jsonify({"status": "error", "message": "Username required"}), 400
            
        delete_user_task(username)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error stopping schedule: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/schedule/status", methods=["GET"])
def schedule_status():
    """Get status of scheduled tasks for a user"""
    try:
        username = request.args.get('username')
        if not username:
            return jsonify({"status": "error", "message": "Username required"}), 400
            
        tasks = load_user_tasks(username).get("tasks", [])
        return jsonify({
            "status": "success" if tasks else "no task",
            "tasks": tasks
        })
    except Exception as e:
        logger.error(f"Error checking schedule status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting backend service on {Config.FLASK_HOST}:{Config.FLASK_PORT}")
    app.run(
        debug=Config.FLASK_DEBUG,
        host=Config.FLASK_HOST,
        port=Config.FLASK_PORT
    )