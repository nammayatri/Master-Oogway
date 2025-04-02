import re
import logging
import threading
import uvicorn
import requests
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, BackgroundTasks, Query, Form, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Dict, List, Union
import sys
import time

from metrics_fetcher import MetricsFetcher
from load_config import load_config
from slack import SlackMessenger
from home import home_res
from master_oogway import (
    get_master_oogway_insights,
    get_master_oogway_summarise_text,
    call_dolphin
)


# -------------------- Load Configuration -------------------- #
config = load_config()
SLACK_THREAD_API = config.get("SLACK_THREAD_API")
SLACK_BOT_TOKEN = config.get("SLACK_BOT_TOKEN")
SCHEDULE_INTERVAL_DAYS = config.get("SCHEDULE_INTERVAL_DAYS", 1)
SCHEDULE_TIME = config.get("SCHEDULE_TIME", "00:00")
TIME_ZONE = config.get("TIME_ZONE", "Asia/Kolkata")
ALLOWED_USER_IDS = set(config.get("ALLOWED_USER_IDS", []))
IGNORED_USER_IDS = set(config.get("IGNORED_USER_IDS", []))
HOST = config.get("HOST", "localhost")
PORT = config.get("PORT", 8000)
ALERT_CHANNEL_NAME = config.get("ALERT_CHANNEL_NAME", "#somechannel")
SLACK_USER_API = "https://slack.com/api/users.info"
SLACK_USERS_LIST_API = "https://slack.com/api/users.list"
API_KEYS = set(config.get("API_KEYS", []))  # API Keys should be stored securely
API_ENDPOINT = config.get("API_ENDPOINT", "")
CACHE_TTL = 3600 * config.get("CACHE_TTL", 1) 
MAX_SIZE_BYTES = 1024 * 1024 * config.get("MAX_SIZE_MB", 10)

IST = pytz.timezone(TIME_ZONE)
SCHEDULE_HOUR, SCHEDULE_MINUTE = map(int, SCHEDULE_TIME.split(":"))

# -------------------- Initialize FastAPI & Services -------------------- #
app = FastAPI()
scheduler = BackgroundScheduler(timezone=IST)
metrics_fetcher = MetricsFetcher()
slack_messenger = SlackMessenger(config)

global_user_map = None
thread_cache: Dict[tuple[str, str], Dict[str, Union[List, float]]] = {}


# -------------------- Helper Functions -------------------- #

def handle_user_auth(user_id,bot_id, user_name):
    """Handles user authentication and returns True if user is authorized."""
    if user_id in ALLOWED_USER_IDS or bot_id in ALLOWED_USER_IDS or user_name in ALLOWED_USER_IDS:
        return True
    return False

def handle_slack_message(event,channel_id=None,text=None):
    """Handles incoming Slack messages and triggers appropriate functions."""
    user_id = event.get("user")
    user_name = event.get("username")
    channel_id = event.get("channel",channel_id)
    bot_id = event.get("bot_id")
    if not handle_user_auth(user_id, bot_id, user_name) and text is None:
        logging.warning(f"❌ Unauthorized User: {user_id}")
    text = (text or str(event)).lower()
    thread_ts = event.get("ts")

    if handle_alb_5xx_error(text):
        slack_messenger.send_message(
            channel=channel_id,
            text="🚨 ALB 5xx or ODC errors detected. Fetching error report and service performance metrics — results will be posted shortly.",
            thread_ts=thread_ts
        )
        metrics_fetcher.get_current_5xx_or_0DC(thread_ts=thread_ts, channel_id=channel_id)
        return

    if handle_redis_memory_error(text):
        slack_messenger.send_message(
            channel=channel_id,
            text="🚨 Redis memory issue detected. Fetching Redis and application performance metrics — results will be posted shortly.",
            thread_ts=thread_ts
        )
        metrics_fetcher.get_current_metrics(thread_ts=thread_ts, channel_id=channel_id)
        return

    if handle_db_alerts(text):
        slack_messenger.send_message(
            channel=channel_id,
            text="🚨 Database alert detected `High CPU`. Fetching database and application performance metrics — results will be posted shortly.",
            thread_ts=thread_ts
        )
        metrics_fetcher.get_current_metrics(thread_ts=thread_ts, channel_id=channel_id)

    if handle_ride_to_search(text):
        slack_messenger.send_message(
            channel=channel_id,
            text="🚨 Significant drop detected in ride-to-search ratio. Fetching service performance and error metrics — results will be posted shortly.",
            thread_ts=thread_ts
        )
        metrics_fetcher.get_current_5xx_or_0DC(thread_ts=thread_ts, channel_id=channel_id)


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



def fetch_all_users(headers):
    global global_user_map
    if global_user_map is not None:
        logging.info("🌐 Using cached user map")
        return global_user_map
    user_map = {}
    params = {"limit": 1000}  # 500 users fit in one call
    logging.info("🔍 Fetching all users from Slack...")
    response = requests.get(SLACK_USERS_LIST_API, headers=headers, params=params)
    if response.status_code == 200 and response.json().get("ok"):
        for user in response.json().get("members", []):
            name = user.get("real_name") or user.get("profile", {}).get("display_name") or user.get("name", user["id"])
            user_map[user["id"]] = name
    else:
        logging.warning(f"❌ Failed to fetch users: {response.status_code} - {response.text}")
    global_user_map = user_map
    return user_map

def get_object_size(obj, seen=None) -> int:
    """Recursively estimate the memory size of an object in bytes."""
    if seen is None:
        seen = set()
    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)
    size = sys.getsizeof(obj)
    if isinstance(obj, dict):
        size += sum(get_object_size(k, seen) + get_object_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set)):
        size += sum(get_object_size(item, seen) for item in obj)
    return size

def prune_thread_cache(force=False):
    """Prune threads exceeding 10MB or older than 1 hour."""
    current_time = time.time()
    to_remove = []
    for key, entry in thread_cache.items():
        age_seconds = current_time - entry["timestamp"]
        is_expired = age_seconds > CACHE_TTL
        entry_size = get_object_size(entry)
        is_oversized = entry_size > MAX_SIZE_BYTES
        if force or is_expired or is_oversized:
            to_remove.append((key, age_seconds, entry_size))
    for key, age, size in to_remove:
        del thread_cache[key]
        logging.info(f"Pruned thread {key}: age={age:.1f}s, size={size / (1024 * 1024):.2f}MB")
    if to_remove:
        logging.info(f"Pruned {len(to_remove)} threads from cache")

def get_thread_messages(event, return_messages=False) -> Union[str, List]:
    """Fetches thread messages with caching, replacing user IDs with names."""
    channel_id = event["channel"]
    thread_ts = event.get("thread_ts") or event["ts"]
    cache_key = (channel_id, thread_ts)
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}", "Content-Type": "application/json"}
    
    cached_entry = thread_cache.get(cache_key)
    current_time = time.time()
    if cached_entry and (current_time - cached_entry["timestamp"]) < CACHE_TTL:
        logging.info(f"Cache hit for thread {thread_ts} in channel {channel_id}")
        messages = cached_entry["messages"]
    else:
        # Cache miss or expired: fetch from Slack API
        logging.info(f"Cache miss for thread {thread_ts} in channel {channel_id}")
        params = {"channel": channel_id, "ts": thread_ts}
        response = requests.get(SLACK_THREAD_API, headers=headers, params=params)
        if response.status_code != 200 or not response.json().get("ok"):
            logging.warning(f"❌ Failed to fetch thread: {response.status_code} - {response.text}")
            return "" if not return_messages else []
        
        messages = response.json().get("messages", [])
        # Store in cache
        thread_cache[cache_key] = {
            "messages": messages,
            "timestamp": current_time
        }
        logging.info(f"Cache updated for thread {thread_ts} in channel {channel_id}")
    if return_messages:
        return messages
    
    user_map = fetch_all_users(headers)
    message_log = []
    user_id_pattern = r"<@U[A-Z0-9]+>"
    for msg in messages:
        user_id = msg.get("user", "Unknown")
        if user_id in config.get("IGNORED_USER_IDS", []):  # Assuming config exists
            continue
        text = msg.get("text", "")
        prefix = f"{user_map.get(user_id, user_id)}: "
        for match in re.findall(user_id_pattern, text):
            clean_id = match.strip("<@>")
            text = text.replace(match, user_map.get(clean_id, clean_id))
        message_log.append(f"{prefix}{text}")
    
    return "\n".join(message_log).strip()


def call_oogway(event):
    """Fetches Oogway's wisdom and sends it as a thread reply."""
    cleaned_text = extract_text_from_event(event)
    try:
        if "detect issue!" in cleaned_text:
            thread_messages = get_thread_messages(event, return_messages=True)
            print("🔍 Detecting Issue... thread text ->>", str(thread_messages))
            slack_messenger.send_message(channel=event["channel"], text="🔍 Detecting Issue...... Please wait!!!", thread_ts=event.get("ts"))
            handle_slack_message(event, text=str(thread_messages), channel_id=event["channel"])
            return
        
        thread_text = get_thread_messages(event)
        if "please summarize!" in cleaned_text:
            print("🐢 Summarizing Text...")
            cleaned_text = cleaned_text.replace("please summarize!","").strip()
            oogway_message = get_master_oogway_summarise_text(thread_text, cleaned_text)
            slack_messenger.send_message(channel=event["channel"], text=oogway_message, thread_ts=event.get("ts"))
            return
        elif "usedolphin" in cleaned_text:
            cleaned_text = cleaned_text.replace("usedolphin","").strip()
            print("🐬 Fetching Dolphin's Response...")
            # Include thread context in prompt
            full_prompt = f"Thread context:\n{thread_text}\n\nCurrent query: {cleaned_text}"
            dolphin_message = call_dolphin(full_prompt)
            slack_messenger.send_message(channel=event["channel"], text=dolphin_message, thread_ts=event.get("ts"))
            return
        else:
            print("🐢 Fetching Oogway's Quote...")
            # Include thread context in prompt
            full_prompt = f"Thread context:\n{thread_text}\n\nCurrent query: {cleaned_text}"
            oogway_message = get_master_oogway_insights(prompt=full_prompt)
            slack_messenger.send_message(channel=event["channel"], text=oogway_message, thread_ts=event.get("ts"))
            return
    except Exception as e:
        logging.error(f"❌ Error fetching Oogway's quote: {e}")

def start_pruning():
    logging.info("🌳 Starting Cache Pruning Thread...")
    def periodic_prune():
        while True:
            prune_thread_cache()
            time.sleep(60*20)  # Prune every 20 minutes
    threading.Thread(target=periodic_prune, daemon=True).start()

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
    bot_id = event.get("bot_id")
    
    if "challenge" in event_data:
        return JSONResponse({"challenge": event_data["challenge"]})
    
    print("🔗 Received Slack Event:", event_data)
    if (user_id is None and bot_id is None) or (user_id in IGNORED_USER_IDS or bot_id in IGNORED_USER_IDS):
        reason = "No valid user or bot" if (user_id is None and bot_id is None) else "Ignored User or Bot"
        logging.warning(f"❌ {reason}: user_id={user_id}, bot_id={bot_id}, event={event}")
        return JSONResponse({"status": "ok", "message": reason})
    
    event = event_data.get("event", {})

    if event.get("type") == "message":
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
            # slack_messenger.send_message(text=f"Master Oogway :oogway: is  🔍 Fetching Current Metrics...  Results will be posted here soon.",channel=channel_id,thread_ts=thread_ts)
            background_tasks.add_task(metrics_fetcher.get_current_metrics, thread_ts=thread_ts,channel_id=channel_id, time_delta=time_delta)
            return JSONResponse({"response_type": "in_channel", "text": "🔍 Fetching Current Metrics...  Results will be posted here soon."})
        
        elif command == "/generate_5xx_0dc_report":
            text = text.strip().lower()
            time_delta = int(text.split(" ")[0]) if text else None
            # slack_messenger.send_message(text=f"Master Oogway :oogway: is  🔍 Fetching 5xx or 0DC Metrics... ou will be notified in `{ALERT_CHANNEL_NAME}` channel.",channel=channel_id,thread_ts=thread_ts)
            background_tasks.add_task(metrics_fetcher.get_current_5xx_or_0DC, thread_ts=thread_ts,channel_id=channel_id, time_delta=time_delta)
            return JSONResponse({"response_type": "in_channel", "text": "🔍 Fetching 5xx or 0DC Metrics...  Results will be posted here soon."})
        
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
            response_text = f":oogway: ✅ Anomaly Detection Triggered! Fetching and analyzing metrics.... Results will be posted here soon."
            # slack_messenger.send_message(text=response_text,channel=channel_id)
            background_tasks.add_task(metrics_fetcher.fetch_and_analyze_all_metrics,thread_ts=thread_ts,channel_id=channel_id,now_time_delta=now_time_delta,time_delta=time_delta,time_offset_days=past_time_delta)
            return JSONResponse({"response_type": "in_channel", "text": response_text})
        else:
            return JSONResponse({"response_type": "in_channel", "text": "❌ Invalid command"})
    except Exception as e:
        logging.error(f"❌ Error processing Slack command: {e}")
        return JSONResponse({"response_type": "in_channel", "text": "❌ Error processing command"})



# -------------------- Scheduled Tasks -------------------- #
def scheduled_fetch():
    """Fetches metrics automatically at the scheduled time."""
    logging.info(f"⏳ Scheduled Metrics Fetch at {SCHEDULE_TIME} IST")
    metrics_fetcher.fetch_and_analyze_all_metrics()


# -------------------- Start Scheduler -------------------- #
scheduler.add_job(scheduled_fetch, "cron", day=f"*/{SCHEDULE_INTERVAL_DAYS}", hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=IST)

try:
    scheduler.start()
    next_run = scheduler.get_jobs()[0].next_run_time if scheduler.get_jobs() else "No jobs scheduled"
    logging.info(f"✅ Scheduler Started. Next Run: {next_run}")
except Exception as e:
    logging.error(f"❌ Error starting scheduler: {e}")


if __name__ == "__main__":
    start_pruning()
    uvicorn.run(app, host=HOST, port=PORT)