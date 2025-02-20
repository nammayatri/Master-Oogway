import json
import os
import base64

CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "config.json"))

CONFIG_ENV_DATA = os.getenv("CONFIG_ENV_DATA")

def load_config():
    """Load config.json and return it as a dictionary."""
    print(f"Loading config from {CONFIG_FILE}")
    try:
        if CONFIG_ENV_DATA:
            #  its a base64 encoded string
            decoded_config = base64.b64decode(CONFIG_ENV_DATA).decode("utf-8")
            config = json.loads(decoded_config)
            print(f"✅ Loaded config from environment variable\n")
            return config
        else:
            with open(CONFIG_FILE, "r") as file:
                config = json.load(file)
            print(f"✅ Loaded config from {CONFIG_FILE}\n")
            return config
    except FileNotFoundError:
        print(f"❌ ERROR: Missing configuration file: {CONFIG_FILE}")
        exit(1)
    except json.JSONDecodeError:
        print(f"❌ ERROR: Invalid JSON format in {CONFIG_FILE}")
        exit(1)

if __name__ == "__main__":
    load_config()