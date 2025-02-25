import random
import requests
import logging
from load_config import load_config
from openai import OpenAI


config = load_config()
# Set your Gemini API key here (or load from env)
GEMINI_API_KEY = config.get("GEMINI_API_KEY")
DOLPHIN_API_KEY = config.get("DOLPHIN_API_KEY")

# API URL for Gemini
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# API URL for ReliableSoft AI
RELIABLESOFT_API_URL = "https://www.reliablesoft.net/wp-admin/admin-ajax.php"


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

    str_data = [x for x in other_data.items()] if other_data else []
    string_data = str(str_data)

    data = {
        "action": "openai_process",
        "text": (
            "You are Master Oogway from Kung Fu Panda, a wise and funny Kung Fu master. "
            "Give a **tech-related** quote that is **simple, funny, and full of wisdom**. "
            "Use **easy words, daily life examples, and desi-style humor**. "
            "Make it sound like an **old wise man giving life advice**, but related to **coding, software, startups, or tech jobs**. "
            "Remember, **simple, funny, and wise**. "
            "It should be short and easy to understand. like an indian engineer english."
            + (f" Use this extra information while creating the quote: {string_data}" if other_data else "")
        ),
        "language": "English",
        "ideas": "1",
        "tone": "Witty, Simple, Wise",
        "model": "gpt-3.5-turbo",
        "length": "1",
        "temperature": "0.6"
    }

    try:
        response = requests.post(RELIABLESOFT_API_URL,
                                 headers=headers, data=data)
        response.raise_for_status()
        json_data = response.json()
        if json_data.get("success") and json_data.get("data"):
            quotes_text = json_data["data"]["data"]["choices"][0]["message"]["content"]
            quotes_list = quotes_text.split("\n\n")  # Split by double newlines
            index = random.randint(0, len(quotes_list) - 1)
            return quotes_list[index].strip()
        else:
            logging.error(
                "❌ Failed to fetch quotes: Unexpected response format")
            return "Master Oogway is silent today... Try again later!"

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error fetching quotes: {e}")
        return "Master Oogway's connection to wisdom is lost... Try again later!"


def get_master_oogway_insights(prompt=""):
    """
    Calls the Gemini API and fetches the best Oogway wisdom quote.

    :param prompt: The wisdom-related question or request.
    :return: A string containing Oogway's wisdom.
    """
    try:
        if not prompt:
            prompt = "Give me a wise and insightful quote."

        data = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }

        response = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json=data
        )

        if response.status_code != 200:
            logging.error(
                f"❌ API Error {response.status_code}: {response.text}")
            return "Master Oogway is silent today... Try again later!"

        response_data = response.json()

        # Extract the best candidate response
        candidates = response_data.get("candidates", [])
        best_response = None

        for candidate in candidates:
            text_parts = candidate.get("content", {}).get("parts", [])
            for part in text_parts:
                if part.get("text"):
                    best_response = part["text"]
                    break
            if best_response:
                break

        if not best_response:
            return "Master Oogway has no words... Perhaps reflect in silence."

        return best_response.strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Request Exception: {e}")
        return "Master Oogway's connection to the universe is lost... Try again later!"


def get_master_oogway_summarise_text(data):
    """
    Calls the Gemini API and fetches the best Oogway wisdom quote.

    :param prompt: The wisdom-related question or request.
    :return: A string containing Oogway's wisdom.
    """
    try:
        data = {
            "contents": [{
                "parts": [{"text": f"Summarize the following slack message data so that anyone could understand what's the context: {data}"}]
            }]
        }

        response = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json=data
        )

        if response.status_code != 200:
            logging.error(
                f"❌ API Error {response.status_code}: {response.text}")
            return "Master Oogway is silent today... Try again later!"

        response_data = response.json()

        # Extract the best candidate response
        candidates = response_data.get("candidates", [])
        best_response = None

        for candidate in candidates:
            text_parts = candidate.get("content", {}).get("parts", [])
            for part in text_parts:
                if part.get("text"):
                    best_response = part["text"]
                    break
            if best_response:
                break

        if not best_response:
            return "Master Oogway has no words... Perhaps reflect in silence."

        return best_response.strip()

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Request Exception: {e}")
        return "Master Oogway's connection to the universe is lost... Try again later!"


def call_dolphin(prompt):
    client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=DOLPHIN_API_KEY
    )
    completion = client.chat.completions.create(
    extra_headers={
        "HTTP-Referer": "<YOUR_SITE_URL>", # Optional. Site URL for rankings on openrouter.ai.
        "X-Title": "<YOUR_SITE_NAME>", # Optional. Site title for rankings on openrouter.ai.
    },
    extra_body={},
    model="cognitivecomputations/dolphin3.0-r1-mistral-24b:free",
    messages=[
        {
        "role": "user",
        "content": prompt
        }
    ]
    )
    return(completion.choices[0].message.content)

