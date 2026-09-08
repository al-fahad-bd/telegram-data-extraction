import re
from datetime import datetime
from typing import Any, Dict, Optional


def parse_bot_response(raw_text: Optional[str], queried_number: str) -> Dict[str, Any]:
    """
    Parses Truecaller bot response into structured dictionary fields.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    data: Dict[str, Any] = {
        "phone_number": queried_number,
        "name": "Not Found",
        "carrier": "Unknown",
        "country": "Unknown",
        "has_whatsapp": False,
        "has_telegram": False,
        "status": "Unknown",
        "timestamp": now,
        "raw_text": raw_text or "",
    }

    if not raw_text:
        data["status"] = "No Response"
        return data

    text = raw_text.strip()

    # Check for rate limit or quota warning
    lower_text = text.lower()
    if "limit" in lower_text or "flood" in lower_text:
        data["status"] = "Rate Limited"
        data["name"] = "Limit Reached"
        return data

    if "need to join" in lower_text:
        data["status"] = "Channel Join Required"
        return data

    if "searching" in lower_text and len(text) < 30:
        data["status"] = "Search Incomplete"
        return data

    # Extract Number
    num_match = re.search(r"Number:\s*\**(\+?\d+)", text, re.IGNORECASE)
    if num_match:
        data["phone_number"] = num_match.group(1).strip()

    # Extract Country (Any country worldwide)
    country_match = re.search(r"Country:\s*\**([^\n\*]+)", text, re.IGNORECASE)
    if country_match:
        c_raw = country_match.group(1).strip()
        c_clean = re.sub(r"[^\w\s\-\.]", "", c_raw).strip()
        data["country"] = c_clean if c_clean else c_raw

    # Extract Carrier
    carrier_match = re.search(r"Carrier:\s*\*+\s*`?([^\n`\*]+)`?", text, re.IGNORECASE) or re.search(r"Carrier:\s*`?([^\n`\*]+)`?", text, re.IGNORECASE)
    if carrier_match:
        data["carrier"] = carrier_match.group(1).strip()

    # Extract Name
    name_match = re.search(r"Name:\s*\*+\s*`?([^\n`\*]+)`?", text, re.IGNORECASE) or re.search(r"Name:\s*`?([^\n`\*]+)`?", text, re.IGNORECASE)
    if name_match:
        extracted_name = name_match.group(1).strip()
        data["name"] = extracted_name
        if extracted_name.lower() in ("not found", "unknown", "none", "n/a"):
            data["status"] = "Not Found"
        else:
            data["status"] = "Found"
    else:
        data["status"] = "Unknown"

    # WhatsApp and Telegram are not verified by the Truecaller bot (it only provides generic links)
    data["has_whatsapp"] = False
    data["has_telegram"] = False

    return data
