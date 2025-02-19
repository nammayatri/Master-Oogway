import uvicorn
import requests
import logging
from fastapi import FastAPI, BackgroundTasks, Query, Form
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import pytz
from metrics_fetcher import MetricsFetcher
from load_config import load_config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fastapi.responses import JSONResponse, HTMLResponse
from slack import SlackMessenger
from home import home_res

# Load configuration
config = load_config()
SCHEDULE_INTERVAL_DAYS = config.get("SCHEDULE_INTERVAL_DAYS", 1)
SCHEDULE_TIME = config.get("SCHEDULE_TIME", "00:00")
TIME_ZONE = config.get("TIME_ZONE", "Asia/Kolkata")

# Timezone setup
IST = pytz.timezone(TIME_ZONE)
SCHEDULE_HOUR, SCHEDULE_MINUTE = map(int, SCHEDULE_TIME.split(":"))

app = FastAPI()
scheduler = BackgroundScheduler(timezone=IST)
metrics_fetcher = MetricsFetcher()
slack_messenger = SlackMessenger(config)

# Slack Bot Configurations
SLACK_BOT_TOKEN = config.get("SLACK_BOT_TOKEN")
API_BASE_URL = config.get("API_BASE_URL", "http://localhost:8000")

slack_client = WebClient(token=SLACK_BOT_TOKEN)
logging.basicConfig(level=logging.INFO)


# ✅ **Scheduled Function - Runs at Configured Time**
def scheduled_fetch():
    """Fetches metrics automatically at the scheduled time."""
    logging.info(f"⏳ Scheduled Metrics Fetch at {SCHEDULE_TIME} IST")
    metrics_fetcher.fetch_and_analyze_all_metrics()


@app.get("/", response_class=HTMLResponse)
def home():
    """Returns an HTML page with Master Oogway's wisdom."""
    return home_res()


# ✅ **API to Manually Trigger Metrics Fetch**
@app.get("/fetch_metrics")
def trigger_metrics_fetch(
    background_tasks: BackgroundTasks,
    time_offset_days: int = Query(None, description="Days before today for fetching past metrics"),
    target_hours: int = Query(None, description="Hour for fetching metrics"),
    target_minutes: int = Query(None, description="Minutes for fetching metrics"),
    start_date_time: str = Query(None, description="Start datetime (YYYY-MM-DD HH:MM:SS)"),
    end_date_time: str = Query(None, description="End datetime (YYYY-MM-DD HH:MM:SS)")
):
    """Manually triggers metrics fetching via API."""
    logging.info("🎯 Manually Triggered Metrics Fetch")
    
    start_dt = datetime.strptime(start_date_time, "%Y-%m-%d %H:%M:%S") if start_date_time else None
    end_dt = datetime.strptime(end_date_time, "%Y-%m-%d %H:%M:%S") if end_date_time else None

    background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics,
                              time_offset_days, target_hours, target_minutes, start_dt, end_dt)

    return JSONResponse({
        "status": "✅ Metrics fetch started in background",
        "time_offset_days": time_offset_days,
        "target_hours": target_hours,
        "target_minutes": target_minutes,
        "start_date_time": start_date_time,
        "end_date_time": end_date_time
    })

# get_current_5xx_or_0DC(self,start_time=None,end_time=None,time_delta=None):
@app.get("/fetch_current_metrics")
def trigger_current_metrics_fetch(
    background_tasks: BackgroundTasks,
    start_time: str = Query(None, description="Start time (HH:MM)"),
    end_time: str = Query(None, description="End time (HH:MM)"),
    time_delta: int = Query(None, description="Time delta in minutes")
):
    """Manually triggers metrics fetching via API."""
    logging.info("🎯 Manually Triggered Metrics Fetch")
    
    background_tasks.add_task(metrics_fetcher.get_current_5xx_or_0DC,start_time,end_time,time_delta)

    return JSONResponse({
        "status": "✅Current Metrics fetch started in background",
        "start_time": start_time,
        "end_time": end_time,
        "time_delta": time_delta
    })
    

@app.get("/fetch_current_report")
def trigger_current_report_fetch(
    background_tasks: BackgroundTasks,
    start_time: str = Query(None, description="Start time (HH:MM)"),
    end_time: str = Query(None, description="End time (HH:MM)"),
    time_delta: int = Query(None, description="Time delta in minutes")
):
    """Manually triggers metrics fetching via API."""
    logging.info("🎯 Manually Triggered Metrics Fetch")
    
    background_tasks.add_task(metrics_fetcher.get_current_metrics,start_time,end_time,time_delta)

    return JSONResponse({
        "status": "✅Current Metrics fetch started in background",
        "start_time": start_time,
        "end_time": end_time,
        "time_delta": time_delta
    })

# ✅ **Slack Bot Command Integration (`/fetch_metrics`)**
@app.post("/slack/commands")
def handle_slash_command(
    background_tasks: BackgroundTasks,
    command: str = Form(...),
    text: str = Form("")
):
    """
    Handles the `/fetch_metrics` Slack command and triggers the API.
    """
    logging.info(f"🔗 Received Slack Command: {command} with params: {text}")

    args = text.split()
    params = {
        "time_offset_days": int(args[0]) if len(args) > 0 and args[0].isdigit() else None,
        "target_hours": int(args[1]) if len(args) > 1 and args[1].isdigit() else None,
        "target_minutes": int(args[2]) if len(args) > 2 and args[2].isdigit() else None,
        "start_date_time": args[3] if len(args) > 3 else None,
        "end_date_time": args[4] if len(args) > 4 else None,
    }

    api_url = f"{API_BASE_URL}/fetch_metrics"

    try:
        response = requests.get(api_url, params=params)
        if response.status_code == 200:
            message = "🚀 Metrics fetch triggered successfully!"
            return JSONResponse({"response_type": "ephemeral", "text": message})
        else:
            return JSONResponse({"response_type": "ephemeral", "text": "❌ Failed to trigger metrics fetch!"})

    except Exception as e:
        logging.error(f"❌ Error calling API: {e}")
        return JSONResponse({"response_type": "ephemeral", "text": "❌ Failed to fetch metrics!"})


def send_slack_message(channel, message):
    """Sends a message to Slack."""
    try:
        slack_client.chat_postMessage(channel=channel, text=message)
    except SlackApiError as e:
        logging.error(f"Slack API Error: {e.response['error']}")


# ✅ **Start Scheduler for Auto Trigger at 12 AM IST**
scheduler.add_job(
    scheduled_fetch,
    "cron",
    hour=SCHEDULE_HOUR,   # Runs at 12 AM IST
    minute=SCHEDULE_MINUTE,
    timezone=IST
)

scheduler.start()
logging.info(f"✅ Scheduler Started. Next Run: {scheduler.get_jobs()[0].next_run_time}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)