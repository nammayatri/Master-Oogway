import re
import string
import math
from collections import Counter

def calculate_entropy(text):
    if not text:
        return 0
    length = len(text)
    freq = Counter(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())

def is_likely_secret_or_id(token, min_entropy=2.5, min_length=6):
    entropy = calculate_entropy(token)
    has_special = any(c in string.punctuation for c in token)
    has_digits = any(c.isdigit() for c in token)
    has_letters = any(c.isalpha() for c in token)
    return (entropy > min_entropy and len(token) >= min_length and 
            (has_special or (has_digits and has_letters)))

def remove_secrets_and_ids(text):
    patterns = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"(\+\d{1,3}\s?)?(\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}",
        "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "url_with_creds": r"(https?://|//)[^/\s]+:[^/\s]+@[\w.-]+",
        "bitcoin": r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b",
        "ethereum": r"\b0x[a-fA-F0-9]{40}\b",
        "ssh_key": r"-----BEGIN [A-Z ]+KEY-----[A-Za-z0-9+/=\s]+-----END [A-Z ]+KEY-----",
        "aws_key": r"\bAKIA[0-9A-Z]{16}\b",
        "uuid": r"\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b",
        "base64": r"\b[A-Za-z0-9+/=]{50,}\b",
        "generic_key": r"\b[a-zA-Z0-9]{20,40}\b",
        "custom_id": r"\b[a-zA-Z0-9]{5,}-[a-zA-Z0-9]{5,}-[a-zA-Z0-9]{5,}(?:-[a-zA-Z0-9]{4,})?\b",
        "short_id": r"\b[a-zA-Z]*\d+[a-zA-Z]*\b", 
        "dashed_id": r"\b[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+\b", 
        "session_id": r"\b[sS][iI][dD]=[a-zA-Z0-9]{8,}\b", 
    }
    
    redacted_text = text
    for pattern in patterns.values():
        redacted_text = re.sub(pattern, "xxxxxxxxxx", redacted_text)
    redacted_text = re.sub(r"(?i)(password|secret|key|token|pwd|auth|id|sid)=[^&\s]+", r"\1=xxxxxxxxxx", redacted_text)
    tokens = re.findall(r'"[^"]*"|[^\s"]+', redacted_text)
    for token in tokens:
        if "xxxxxxxxxx" in token:
            continue
        cleaned_token = re.sub(r"[^\w]", "", token.strip('"'))
        if is_likely_secret_or_id(cleaned_token):
            redacted_text = redacted_text.replace(token, "xxxxxxxxxx")
    return redacted_text
