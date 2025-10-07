import requests
from datetime import datetime
import json

DEFAULT_TIMEOUT = 5  # Sekunden

def build_timestamp():
    """ISO-8601 Timestamp mit lokalem Offset."""
    return datetime.now().astimezone().isoformat()

def send_message(server_post_url, from_user, to_user, message, timeout=DEFAULT_TIMEOUT):
    """
    Sendet eine Nachricht per HTTP POST an server_post_url.
    Erwarteter Request-Body (JSON):
      { "from": "...", "to": "...", "timestamp": "...", "message": "..." }

    Rückgabe:
      (True, parsed_json) bei HTTP 2xx,
      (False, {"status_code": int, "body": ...}) bei Nicht-2xx,
      (False, {"error": "..."}) bei Netzwerk-/Parsingfehlern.
    """
    payload = {
        "from": from_user,
        "to": to_user,
        "timestamp": build_timestamp(),
        "message": message,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        resp = requests.post(server_post_url, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as e:
        return False, {"error": str(e)}

    if 200 <= resp.status_code < 300:
        # versuche JSON zu parsen, fallback auf Text
        try:
            return True, resp.json()
        except ValueError:
            return True, {"text": resp.text}
    else:
        try:
            body = resp.json()
        except ValueError:
            body = resp.text
        return False, {"status_code": resp.status_code, "body": body}