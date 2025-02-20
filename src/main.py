import uvicorn
import logging
from fastapi import FastAPI, BackgroundTasks, Query, Form, Request, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
from metrics_fetcher import MetricsFetcher
from load_config import load_config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from fastapi.responses import JSONResponse, HTMLResponse
from slack import SlackMessenger
from home import home_res
from master_oogway import get_master_oogway_gemini_quotes
import re

# Load Configuration
config = load_config()
SCHEDULE_INTERVAL_DAYS = config.get("SCHEDULE_INTERVAL_DAYS", 1)
SCHEDULE_TIME = config.get("SCHEDULE_TIME", "00:00")
TIME_ZONE = config.get("TIME_ZONE", "Asia/Kolkata")
ALLOWED_USER_IDS = config.get("ALLOWED_USER_IDS", [])
HOST = config.get("HOST", "localhost")
PORT = config.get("PORT", 8000)
ALERT_CHANNEL_NAME = config.get("ALERT_CHANNEL_NAME", "#namma-yatri-sre")

IST = pytz.timezone(TIME_ZONE)
SCHEDULE_HOUR, SCHEDULE_MINUTE = map(int, SCHEDULE_TIME.split(":"))

app = FastAPI()
scheduler = BackgroundScheduler(timezone=IST)
metrics_fetcher = MetricsFetcher()
slack_messenger = SlackMessenger(config)

# ------------------------------------------------------ API Endpoints ------------------------------------------------------ #
@app.get("/", response_class=HTMLResponse)
def home():
    """Returns an HTML page with Master Oogway's wisdom."""
    return home_res()


# Slack Events API Listener (Handles Messages)
@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    event_data = await request.json()
    user_id = event_data.get("event", {}).get("user",None)
    if user_id is None or not handle_user_auth(user_id):
        logging.warning(f"❌ Unauthorized User: {user_id}")
        return JSONResponse({"status": "ok", "message": "Unauthorized User"})
    
    print("🔗 Received Slack Event:", event_data)

    if "challenge" in event_data:
        return JSONResponse({"challenge": event_data["challenge"]})
    event = event_data.get("event", {})

    if event.get("type") == "message" and event.get("subtype") is None:
        background_tasks.add_task(handle_slack_message, event)
        print("🐢 Oogway's Wisdom Sent in Thread")
    if event.get("type") == "app_mention":
        background_tasks.add_task(send_oogway_quote, event)
        print("🐢 Oogway's Wisdom Sent in Thread")
    return JSONResponse({"status": "ok"})


@app.get("/fetch_metrics")
def trigger_metrics_fetch(background_tasks: BackgroundTasks):
    """Manually triggers metrics fetching via API (calls function directly)."""
    logging.info("🎯 Manually Triggered Metrics Fetch")
    background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics)
    return JSONResponse({"status": "✅ Metrics fetch started in background"})


# Slack Slash Command (/fetch_metrics)
@app.post("/slack/commands")
def handle_slash_command(
    background_tasks: BackgroundTasks,
    command: str = Form(...),
    text: str = Form("")
):
    """Handles /fetch_metrics Slack command by calling the function directly."""
    logging.info(f"🔗 Received Slack Command: {command} with params: {text}")
    
    if command == "/generate_current_report":
        text = text.strip().lower()
        background_tasks.add_task(metrics_fetcher.get_current_metrics)
        slack_messenger.send_message(text="🔍 Fetching Current Metrics...")
        return JSONResponse({"response_type": "in_channel", "text": f"Master Oogway :oogway: is  🔍 Fetching Current Metrics... You will be notified in {ALERT_CHANNEL_NAME} channel."})
    
    elif command == "/generate_5xx_0dc_report":
        text = text.strip().lower()
        background_tasks.add_task(metrics_fetcher.get_current_5xx_or_0DC)
        slack_messenger.send_message(text=f"Master Oogway :oogway: is  🔍 Fetching 5xx or 0DC Metrics... ou will be notified in {ALERT_CHANNEL_NAME} channel.") 
        return JSONResponse({"response_type": "in_channel", "text": "🔍 Fetching 5xx or 0DC Metrics..."})
    
    elif command == "/fetch_anamoly":
        logging.info("📡 Triggering Metrics Fetch Function...")
        background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics)
        response_text = f":oogway: ✅ Anomaly Detection Triggered! Fetching and analyzing metrics....You will be notified in {ALERT_CHANNEL_NAME} channel."
        slack_messenger.send_message(text=response_text)
        return JSONResponse({"response_type": "in_channel", "text": response_text})
    else:
        return JSONResponse({"response_type": "in_channel", "text": "❌ Invalid command"})


# --------------------------------------------------------- Functions --------------------------------------------------------- #

# Scheduled Function - Runs at Configured Time
def scheduled_fetch():
    """Fetches metrics automatically at the scheduled time."""
    logging.info(f"⏳ Scheduled Metrics Fetch at {SCHEDULE_TIME} IST")
    metrics_fetcher.fetch_and_analyze_all_metrics()

def handle_user_auth(user_id):
    """Handles user authentication and returns True if user is authorized."""
    if user_id in ALLOWED_USER_IDS:
        return True
    return False

def handle_slack_message(event):
    """Handles incoming Slack messages and triggers appropriate functions."""
    user_id = event.get("user")
    if not handle_user_auth(user_id):
        logging.warning(f"❌ Unauthorized User: {user_id}")
        return
    text = event.get("text", "").lower()
    channel_id = event["channel"]
    thread_ts = event.get("ts")
    if handle_alb_5xx_error(text):
        metrics_fetcher.get_current_5xx_or_0DC()
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching 5xx or ODC error report. It will be sent shortly in {ALERT_CHANNEL_NAME}", thread_ts = thread_ts)
        return
    if handle_redis_memory_error(text):
        metrics_fetcher.get_current_metrics()
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching Redis and Application report. It will be sent shortly in {ALERT_CHANNEL_NAME}", thread_ts=thread_ts)
        return
    return
        
        
def handle_redis_memory_error(text):
    if "cloudwatch" in text and "alarm" in text and "redis" in text:
        return True
    return False

def handle_alb_5xx_error(text):
    if "cloudwatch" in text and "alarm" in text and "5xx" in text:
        return True
    return False

def extract_text_from_event(event):
    raw_text = event.get("text", "")
    cleaned_text = re.sub(r"<@U[A-Z0-9]+>", "", raw_text).strip()
    return cleaned_text

def send_oogway_quote(event):
    """Fetches Oogway's wisdom and sends it as a thread reply."""
    cleaned_text = extract_text_from_event(event)
    try:
        print("🐢 Fetching Oogway's Quote...")
        oogway_message = get_master_oogway_gemini_quotes(prompt=cleaned_text)
        slack_messenger.send_message(channel=event["channel"], text=oogway_message, thread_ts=event.get("ts"))
    except Exception as e:
        logging.error(f"❌ Error fetching Oogway's quote: {e}")


# Start Scheduler for Auto Trigger at Configured Time
scheduler.add_job(scheduled_fetch, "cron", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=IST)
scheduler.start()
logging.info(f"✅ Scheduler Started. Next Run: {scheduler.get_jobs()[0].next_run_time}")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)