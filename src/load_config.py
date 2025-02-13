import json
import os

CONFIG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config", "config.json"))

def load_config():
    """Load config.json and return it as a dictionary."""
    print(f"Loading config from {CONFIG_FILE}")
    try:
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