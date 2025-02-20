import requests
import logging
from load_config import load_config

config = load_config()
# Set your Gemini API key here (or load from env)
GEMINI_API_KEY = config.get("GEMINI_API_KEY")

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
        "text": "You are Master Oogway from Kung Fu Panda. Generate a conclusion statement that is funny and wise."
                + (f" Generate a funny statement using this data: {string_data}" if other_data else ""),
        "language": "English",
        "ideas": "1",
        "tone": "Funny Insightful",
        "model": "gpt-3.5-turbo",
        "length": "1",
        "temperature": "0.5"
    }

    try:
        response = requests.post(RELIABLESOFT_API_URL, headers=headers, data=data)
        response.raise_for_status()

        json_data = response.json()

        if json_data.get("success") and json_data.get("data"):
            quotes_text = json_data["data"]["data"]["choices"][0]["message"]["content"]
            quotes_list = quotes_text.split("\n\n")  # Split by double newlines
            return quotes_list[0]
        else:
            logging.error("❌ Failed to fetch quotes: Unexpected response format")
            return "Master Oogway is silent today... Try again later!"

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Error fetching quotes: {e}")
        return "Master Oogway's connection to wisdom is lost... Try again later!"

def get_master_oogway_gemini_quotes(prompt=""):
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
                "parts": [{"text": f"You are Master Oogway. if prompt is about talking then talk else give the best reply suitable, prompt is : {prompt}"}]
            }]
        }

        response = requests.post(
            GEMINI_API_URL,
            headers={"Content-Type": "application/json"},
            json=data
        )

        if response.status_code != 200:
            logging.error(f"❌ API Error {response.status_code}: {response.text}")
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
    