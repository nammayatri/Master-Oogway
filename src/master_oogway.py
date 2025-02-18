import requests

def get_master_oogway_quotes(other_data=None):
    """
    Fetches funny and wise quotes from Master Oogway using the ReliableSoft AI Quote Generator API.
    """
    url = "https://www.reliablesoft.net/wp-admin/admin-ajax.php"
    
    headers = {
        "accept": "*/*",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "origin": "https://www.reliablesoft.net",
        "referer": "https://www.reliablesoft.net/ai-text-generator-tools/quote-generator/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
        "x-requested-with": "XMLHttpRequest"
    }
    str_data = [x for x in other_data.items()]
    string_data = str(str_data)
    data = {
        "action": "openai_process",
        "text": "You are Master Oogway from Kung Fu Panda.Generate a conclusion statement that is funny and wise." + ("Generate a funny statement using this data go through all the data and then only return output : " + string_data if other_data else ""),
        "language": "English",
        "ideas": "1",
        "tone": "Funny Insighful",
        "model": "gpt-3.5-turbo",
        "length": "1",
        "temperature": "0.5"
    }

    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()  # Raise an error for bad responses

        json_data = response.json()

        # Extract quotes from response
        if json_data.get("success") and json_data.get("data"):
            quotes_text = json_data["data"]["data"]["choices"][0]["message"]["content"]
            quotes_list = quotes_text.split("\n\n")  # Split by double newlines

            return quotes_list[0]

        else:
            print("❌ Failed to fetch quotes: Unexpected response format")
            return ""

    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching quotes: {e}")
        return ""

