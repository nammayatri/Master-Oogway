import random
import requests
import logging
from load_config import load_config
from openai import OpenAI
from safe_secrets import remove_secrets_and_ids

# Load API keys from config
config = load_config()
GEMINI_API_KEY = config.get("GEMINI_API_KEY")
DOLPHIN_API_KEY = config.get("DOLPHIN_API_KEY")
GEMINI_MODEL = config.get("GEMINI_MODEL")

# Gemini API Endpoints
GEMINI_API_URLS = {
    "2.0": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
    "1.5": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
}

# ReliableSoft API URL
RELIABLESOFT_API_URL = "https://www.reliablesoft.net/wp-admin/admin-ajax.php"


# ---------------------- Gemini API Helper ---------------------- #
# ---------------------- Gemini API Helper ---------------------- #
def call_gemini_api(prompt, model=GEMINI_MODEL):
    """Calls Gemini API (2.0 first, then 1.5 if 2.0 fails or limit is exhausted)."""
    if not GEMINI_API_KEY:
        return "❌ Missing Gemini API Key."

    prompt = remove_secrets_and_ids(prompt)
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(GEMINI_API_URLS[model], headers={"Content-Type": "application/json"}, json=data)
        response.raise_for_status()
        return extract_gemini_response(response.json())

    except requests.RequestException as e:
        if response.status_code == 429:  # Rate limit exceeded
            return call_gemini_api(prompt, model="1.5")

        if model == "2.0":  # Any other error → Try 1.5
            return call_gemini_api(prompt, model="1.5")

    return "Master Oogway is silent today... Try again later!"

def extract_gemini_response(response_data):
    """
    Extracts and returns the best response from Gemini API response JSON.
    """
    candidates = response_data.get("candidates", [])
    for candidate in candidates:
        for part in candidate.get("content", {}).get("parts", []):
            if text := part.get("text"):
                return text.strip()

    return "Master Oogway has no words... Perhaps reflect in silence."


# ---------------------- Oogway Quote Generator ---------------------- #
def get_master_oogway_quotes(other_data=None):
    """
    Fetches funny and wise quotes from Master Oogway using the ReliableSoft AI Quote Generator API.
    """
    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://www.reliablesoft.net",
        "referer": "https://www.reliablesoft.net/ai-text-generator-tools/quote-generator/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }

    extra_info = f" Use this extra information: {str(other_data.items())}" if other_data else ""
    data = {
        "action": "openai_process",
        "text": (
            "You are Master Oogway from Kung Fu Panda, a wise and funny Kung Fu master. "
            "Give a **tech-related** quote that is **simple, funny, and full of wisdom**. "
            "Use **easy words, daily life examples, and desi-style humor**. "
            "Make it sound like an **old wise man giving life advice**, but related to **coding, software, startups, or tech jobs**. "
            "It should be very short and easy like one or two liners to understand, like an Indian engineer speaking English."
            + extra_info
        ),
        "language": "English",
        "ideas": "1",
        "tone": "Witty, Simple, Wise",
        "model": "gpt-3.5-turbo",
        "length": "1",
        "temperature": "0.6"
    }

    try:
        response = requests.post(RELIABLESOFT_API_URL, headers=headers, data=data)
        response.raise_for_status()
        json_data = response.json()

        if json_data.get("success") and json_data.get("data"):
            quotes_text = json_data["data"]["data"]["choices"][0]["message"]["content"]
            return random.choice(quotes_text.split("\n\n")).strip()  # Pick a random quote

        logging.error("❌ Failed to fetch quotes: Unexpected response format")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error fetching quotes: {e}")

    return "Master Oogway is silent today... Try again later!"


# ---------------------- Slack Summarization ---------------------- #
def get_master_oogway_summarise_text(data, prompt=""):
    """
    Summarizes Slack messages while preserving important names and context.
    """
    structured_prompt = (
        f"Summarize the following Slack conversation in a simple, clear way. "
        f"Use names of the persons in conversation when relevant. "
        f"Identify key points, decisions, and questions raised.\n\n"
        f"Conversation: {data}"
    )
    
    if prompt:
        structured_prompt += f"\n\nAdditional instructions: {prompt}"
        
    return call_gemini_api(structured_prompt)


def get_master_oogway_insights(prompt):
    """
    Generates insights and advice from Master Oogway using the Gemini API.
    Handles thread context if provided in the prompt.
    """
    # Structure a better prompt for context-aware responses
    if "Thread context:" in prompt:
        parts = prompt.split("Current query:")
        if len(parts) > 1:
            thread_context = parts[0].replace("Thread context:", "").strip()
            query = parts[1].strip()
            structured_prompt = (
                f"Below is a conversation thread from Slack. When answering the latest query, "
                f"consider the full context of the conversation.\n\n"
                f"Conversation history:\n{thread_context}\n\n"
                f"Latest query: {query}\n\n"
                f"Provide a response that acknowledges the context and directly addresses the latest query."
                f"if current query is not related to the thread context, please ignore the thread context and don't say anything about it in your response."
            )
            return call_gemini_api(structured_prompt)
    return call_gemini_api(prompt)

# ---------------------- Dolphin AI Call ---------------------- #
def call_dolphin(prompt):
    """
    Calls Dolphin 3.0 AI model via OpenRouter API.
    """
    if not DOLPHIN_API_KEY:
        logging.error("❌ Missing Dolphin API Key.")
        return "Master Oogway cannot access the Dolphin today."

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=DOLPHIN_API_KEY)
    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "<YOUR_SITE_URL>",
            "X-Title": "<YOUR_SITE_NAME>",
        },
        extra_body={},
        model="cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
        messages=[{"role": "user", "content": prompt}]
    )

    return completion.choices[0].message.content
