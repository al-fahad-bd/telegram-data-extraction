import re
from typing import Dict, List, Optional, Tuple

# Bangladeshi Operator Prefixes
BD_VALID_PREFIXES: Dict[str, str] = {
    "013": "Grameenphone",
    "017": "Grameenphone",
    "014": "Banglalink",
    "019": "Banglalink",
    "018": "Robi",
    "016": "Airtel",
    "015": "Teletalk",
}

# Alias for backwards compatibility
VALID_PREFIXES = BD_VALID_PREFIXES

# Common Global Country Codes and Flag Emojis
GLOBAL_COUNTRY_CODES: Dict[str, Dict[str, str]] = {
    "BD": {"name": "Bangladesh", "code": "+880", "flag": "🇧🇩", "sample": "+8801795664120"},
    "US": {"name": "United States / Canada", "code": "+1", "flag": "🇺🇸", "sample": "+12025550120"},
    "GB": {"name": "United Kingdom", "code": "+44", "flag": "🇬🇧", "sample": "+447911123450"},
    "IN": {"name": "India", "code": "+91", "flag": "🇮🇳", "sample": "+919876543210"},
    "PK": {"name": "Pakistan", "code": "+92", "flag": "🇵🇰", "sample": "+923001234567"},
    "AE": {"name": "United Arab Emirates", "code": "+971", "flag": "🇦🇪", "sample": "+971501234567"},
    "SA": {"name": "Saudi Arabia", "code": "+966", "flag": "🇸🇦", "sample": "+966501234567"},
    "QA": {"name": "Qatar", "code": "+974", "flag": "🇶🇦", "sample": "+97433123456"},
    "KW": {"name": "Kuwait", "code": "+965", "flag": "🇰🇼", "sample": "+96590123456"},
    "MY": {"name": "Malaysia", "code": "+60", "flag": "🇲🇾", "sample": "+60123456789"},
    "SG": {"name": "Singapore", "code": "+65", "flag": "🇸🇬", "sample": "+6581234567"},
    "AU": {"name": "Australia", "code": "+61", "flag": "🇦🇺", "sample": "+61412345678"},
    "DE": {"name": "Germany", "code": "+49", "flag": "🇩🇪", "sample": "+4915123456789"},
    "FR": {"name": "France", "code": "+33", "flag": "🇫🇷", "sample": "+33612345678"},
    "IT": {"name": "Italy", "code": "+39", "flag": "🇮🇹", "sample": "+393123456789"},
    "ES": {"name": "Spain", "code": "+34", "flag": "🇪🇸", "sample": "+34612345678"},
    "TR": {"name": "Turkey", "code": "+90", "flag": "🇹🇷", "sample": "+905321234567"},
    "BR": {"name": "Brazil", "code": "+55", "flag": "🇧🇷", "sample": "+5511912345678"},
    "ID": {"name": "Indonesia", "code": "+62", "flag": "🇮🇩", "sample": "+628123456789"},
    "PH": {"name": "Philippines", "code": "+63", "flag": "🇵🇭", "sample": "+639171234567"},
    "NG": {"name": "Nigeria", "code": "+234", "flag": "🇳🇬", "sample": "+2348031234567"},
    "ZA": {"name": "South Africa", "code": "+27", "flag": "🇿🇦", "sample": "+27821234567"},
    "EG": {"name": "Egypt", "code": "+20", "flag": "🇪🇬", "sample": "+201001234567"},
}


def clean_phone_number(raw_number: str) -> str:
    """
    Cleans and standardizes any international phone number into standard E.164 format (+<digits>).
    Supports all countries worldwide as well as local formats.
    """
    raw = raw_number.strip()
    # Normalize 00 prefix to +
    if raw.startswith("00"):
        raw = "+" + raw[2:]

    # Remove all non-digits except initial +
    has_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)

    if not digits:
        raise ValueError("Phone number contains no digits.")

    # Intelligent local fallback:
    # If user provided a Bangladeshi local format (e.g. 017XXXXXXXX)
    if not has_plus:
        if digits.startswith("880") and len(digits) >= 13:
            return f"+{digits}"
        elif digits.startswith("0") and len(digits) == 11 and digits[:3] in BD_VALID_PREFIXES:
            return f"+88{digits}"
        # Default: treat as international digits without plus
        return f"+{digits}"

    # Standard E.164 length check (7 to 15 digits)
    if len(digits) < 6 or len(digits) > 15:
        raise ValueError(f"Phone number length ({len(digits)} digits) is outside valid international range (6-15 digits).")

    return f"+{digits}"


def is_valid_phone_number(raw_number: str) -> Tuple[bool, str]:
    """
    Validates any international phone number.
    Returns (True, cleaned_number) if valid, or (False, error_message).
    """
    try:
        cleaned = clean_phone_number(raw_number)
        return True, cleaned
    except ValueError as e:
        return False, str(e)


def clean_bd_number(raw_number: str) -> str:
    """
    Cleans and standardizes Bangladeshi phone numbers (kept for backwards compatibility).
    """
    digits = re.sub(r"\D", "", raw_number)
    if digits.startswith("880"):
        digits = digits[2:]
    elif not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits

    if len(digits) != 11:
        raise ValueError(f"Invalid phone number length ({len(digits)} digits). Must be 11 digits like 01712345678.")

    prefix = digits[:3]
    if prefix not in BD_VALID_PREFIXES:
        raise ValueError(f"Invalid Bangladeshi mobile prefix: {prefix}.")

    return f"+88{digits}"


def is_valid_bd_number(raw_number: str) -> Tuple[bool, str]:
    """
    Checks if a number is a valid Bangladeshi number (kept for backwards compatibility).
    """
    try:
        cleaned = clean_bd_number(raw_number)
        return True, cleaned
    except ValueError as e:
        return False, str(e)


def generate_serial_numbers(start_number: str, count: int) -> List[str]:
    """
    Generates a list of serialized phone numbers for ANY country in the world,
    starting from `start_number` and incrementing by 1 sequentially.
    Preserves exact digit length and country calling code.
    """
    cleaned = clean_phone_number(start_number)
    digits_str = cleaned.replace("+", "")
    num_digits = len(digits_str)
    base_int = int(digits_str)

    numbers: List[str] = []
    for i in range(count):
        current_int = base_int + i
        current_digits = f"{current_int:0{num_digits}d}"
        numbers.append(f"+{current_digits}")

    return numbers


def get_operator_from_number(number: str) -> str:
    """
    Returns operator name if Bangladeshi, or detects country code.
    """
    digits = re.sub(r"\D", "", number)
    if digits.startswith("880") and len(digits) >= 6:
        prefix = digits[2:5]
        return BD_VALID_PREFIXES.get(prefix, "Bangladesh (Other)")
    elif digits.startswith("0") and len(digits) == 11:
        prefix = digits[:3]
        return BD_VALID_PREFIXES.get(prefix, "Bangladesh (Other)")

    # Country detection for common prefixes
    for key, cinfo in GLOBAL_COUNTRY_CODES.items():
        code_digits = cinfo["code"].replace("+", "")
        if digits.startswith(code_digits):
            return cinfo["name"]

    return "International"
