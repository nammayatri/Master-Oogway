import uvicorn
import logging
from fastapi import Depends, FastAPI, BackgroundTasks, Query, Form, Request, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
from metrics_fetcher import MetricsFetcher
from load_config import load_config
from fastapi.responses import JSONResponse, HTMLResponse
from slack import SlackMessenger
from home import home_res
from master_oogway import get_master_oogway_insights,get_master_oogway_summarise_text,call_dolphin
import re
import requests

# Load Configuration
config = load_config()
SLACK_THREAD_API = config.get("SLACK_THREAD_API")
SLACK_BOT_TOKEN = config.get("SLACK_BOT_TOKEN")
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
API_KEYS = config.get("API_KEYS", ["your-secure-api-key"])  # Store securely
API_ENDPOINT = config.get("API_ENDPOINT", "")

# ------------------------------------------------------ API Endpoints ------------------------------------------------------ #
@app.get(f"{API_ENDPOINT}", response_class=HTMLResponse)
def home():
    """Returns an HTML page with Master Oogway's wisdom."""
    return home_res()

def verify_api_key(api_key: str = Query(...)):
    if api_key not in API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Slack Events API Listener (Handles Messages)
@app.post(f"{API_ENDPOINT}/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    event_data = await request.json()
    event = event_data.get("event", {})
    user_id = event.get("user")
    if user_id is None or user_id == event.get("bot_id"):
        logging.warning(f"❌ Unauthorized User: {user_id}")
        return JSONResponse({"status": "ok", "message": "Unauthorized User"})
    
    print("🔗 Received Slack Event:", event_data)

    if "challenge" in event_data:
        return JSONResponse({"challenge": event_data["challenge"]})
    event = event_data.get("event", {})

    if event.get("type") == "message" and event.get("subtype") is None:
        background_tasks.add_task(handle_slack_message, event)
    if event.get("type") == "app_mention":
        background_tasks.add_task(call_oogway, event)
    return JSONResponse({"status": "ok"})


@app.get(f"{API_ENDPOINT}/fetch_metrics")
def trigger_metrics_fetch(background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    """Manually triggers metrics fetching via API (calls function directly)."""
    logging.info("🎯 Manually Triggered Metrics Fetch")
    background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics)
    return JSONResponse({"status": "✅ Metrics fetch started in background"})


# Slack Slash Command (/fetch_metrics)
@app.post(f"{API_ENDPOINT}/slack/commands")
def handle_slash_command(
    background_tasks: BackgroundTasks,
    command: str = Form(...),
    text: str = Form(""),
    channel_id: str = Form(""),
    thread_ts: str = Form(""),
):
    """Handles /fetch_metrics Slack command by calling the function directly."""
    logging.info(f"🔗 Received Slack Command: {command} with params: {text}")
    thread_ts = None
    try :
        if "thread_ts" in text:
            thread_ts = text.split("thread_ts=")[-1]
        if command == "/generate_current_report":
            text = text.strip().lower()
            time_delta = int(text.split(" ")[0]) if text else None
            print("time_delta",time_delta)
            # slack_messenger.send_message(text=f"Master Oogway :oogway: is  🔍 Fetching Current Metrics... You will be notified in `{ALERT_CHANNEL_NAME}` channel.",channel=channel_id,thread_ts=thread_ts)
            background_tasks.add_task(metrics_fetcher.get_current_metrics, thread_ts=thread_ts,channel_id=channel_id, time_delta=time_delta)
            return JSONResponse({"response_type": "in_channel", "text": "🔍 Fetching Current Metrics... You will be notified in `#namma-yatri-sre` channel"})
        
        elif command == "/generate_5xx_0dc_report":
            text = text.strip().lower()
            time_delta = int(text.split(" ")[0]) if text else None
            # slack_messenger.send_message(text=f"Master Oogway :oogway: is  🔍 Fetching 5xx or 0DC Metrics... ou will be notified in `{ALERT_CHANNEL_NAME}` channel.",channel=channel_id,thread_ts=thread_ts)
            background_tasks.add_task(metrics_fetcher.get_current_5xx_or_0DC, thread_ts=thread_ts,channel_id=channel_id, time_delta=time_delta)
            return JSONResponse({"response_type": "in_channel", "text": "🔍 Fetching 5xx or 0DC Metrics... You will be notified in `#namma-yatri-sre` channel."})
        
        elif command == "/fetch_anamoly":
            logging.info("📡 Triggering Metrics Fetch Function...")
            args_parts = text.split(" ")
            if len(args_parts) > 2:
                now_time_delta = int(args_parts[0]) if args_parts[0].isdigit() else None
                past_time_delta = int(args_parts[1]) if args_parts[1].isdigit() else None
                time_delta = int(args_parts[2]) if args_parts[2] is not None else None
            else :
                now_time_delta = None
                past_time_delta = None
                time_delta = None
            response_text = f":oogway: ✅ Anomaly Detection Triggered! Fetching and analyzing metrics....You will be notified in `{ALERT_CHANNEL_NAME}` channel."
            # slack_messenger.send_message(text=response_text,channel=channel_id)
            background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics,thread_ts=thread_ts,channel_id=channel_id,now_time_delta=now_time_delta,time_delta=time_delta,time_offset_days=past_time_delta)
            return JSONResponse({"response_type": "in_channel", "text": response_text})
        else:
            return JSONResponse({"response_type": "in_channel", "text": "❌ Invalid command"})
    except Exception as e:
        logging.error(f"❌ Error processing Slack command: {e}")
        return JSONResponse({"response_type": "in_channel", "text": "❌ Error processing command"})


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

def handle_slack_message(event,channel_id=None,text=None):
    """Handles incoming Slack messages and triggers appropriate functions."""
    user_id = event.get("user")
    channel_id = event.get("channel")
    if not handle_user_auth(user_id):
        logging.warning(f"❌ Unauthorized User: {user_id}")
        return
    text = text or event.get("text", "").lower()
    thread_ts = event.get("ts")
    if handle_alb_5xx_error(text):
        metrics_fetcher.get_current_5xx_or_0DC(thread_ts=thread_ts,channel_id=channel_id)
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching 5xx or ODC error report. It will be sent shortly in `{ALERT_CHANNEL_NAME}`", thread_ts = thread_ts)
        return
    if handle_redis_memory_error(text):
        metrics_fetcher.get_current_metrics(thread_ts=thread_ts,channel_id=channel_id)
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching Redis and Application report. It will be sent shortly in `{ALERT_CHANNEL_NAME}`", thread_ts=thread_ts)
        return
    
    if handle_db_alerts(text):
        metrics_fetcher.get_current_metrics(thread_ts=thread_ts,channel_id=channel_id)
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching and analyzing all metrics. It will be sent shortly in `{ALERT_CHANNEL_NAME}`", thread_ts=thread_ts)
    
    if handle_ride_to_search(text):
        metrics_fetcher.get_current_5xx_or_0DC(thread_ts=thread_ts,channel_id=channel_id)
        slack_messenger.send_message(channel=channel_id, text=f"🚨 Fetching and analyzing all metrics. It will be sent shortly in `{ALERT_CHANNEL_NAME}`", thread_ts=thread_ts)
    return


def handle_ride_to_search(text):
    if "ride" in text and "search" in text and "ratio" in text and "down" in text:
        return True
    return False


def handle_db_alerts(text):
    if "cloudwatch" in text and "alarm" in text and "atlas" in text and "high" in text and "cpu" in text:
        return True

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

def get_thread_messages(event):
    """Fetches all messages in the Slack thread where the bot was mentioned, replacing user IDs with names."""
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]  # Use thread_ts if replying, else ts of the message
    headers = {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    params = {"channel": channel_id, "ts": thread_ts}
    response = requests.get(SLACK_THREAD_API, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            messages = data.get("messages", [])
            message_log = []

            for msg in messages:
                text = msg.get("text", "")
                timestamp = msg.get("ts", "")
                message_log.append((text, timestamp))
            formatted_messages = "\n".join([f"{msg[0]} ({msg[1]})" for msg in message_log])
            cleaned_messages = re.sub(r"<@U[A-Z0-9]+>", "", formatted_messages).strip()
            return cleaned_messages.strip() 
    logging.warning("❌ Failed to fetch thread messages")
    return ""

def call_oogway(event):
    """Fetches Oogway's wisdom and sends it as a thread reply."""
    cleaned_text = extract_text_from_event(event)
    try:
        if "please summarize!" in cleaned_text:
            print("🐢 Summarizing Text...")
            thread_text = get_thread_messages(event)
            oogway_message = get_master_oogway_summarise_text(thread_text)
            slack_messenger.send_message(channel=event["channel"], text=oogway_message, thread_ts=event.get("ts"))
        elif "detect issue!" in cleaned_text:
            thread_text = get_thread_messages(event)
            slack_messenger.send_message(channel=event["channel"], text="🔍 Detecting Issue...... Please wait!!!",thread_ts=event.get("ts"))
            handle_slack_message(event,text=thread_text,channel_id=event["channel"])
        elif "usedolphin" in cleaned_text:
            cleaned_text = cleaned_text.replace("usedolphin","").strip()
            print("🐬 Fetching Dolphin's Response...")
            dolphin_message = call_dolphin(cleaned_text)
            slack_messenger.send_message(channel=event["channel"], text=dolphin_message, thread_ts=event.get("ts"))
        else:
            print("🐢 Fetching Oogway's Quote...")
            oogway_message = get_master_oogway_insights(prompt=cleaned_text)
            slack_messenger.send_message(channel=event["channel"], text=oogway_message, thread_ts=event.get("ts"))
    except Exception as e:
        logging.error(f"❌ Error fetching Oogway's quote: {e}")


# Start Scheduler for Auto Trigger at Configured Time
scheduler.add_job(scheduled_fetch, "cron", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=IST)
scheduler.start()
logging.info(f"✅ Scheduler Started. Next Run: {scheduler.get_jobs()[0].next_run_time}")


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)