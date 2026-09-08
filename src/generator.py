import re
from typing import List, Tuple

VALID_PREFIXES = {
    "013": "Grameenphone",
    "017": "Grameenphone",
    "014": "Banglalink",
    "019": "Banglalink",
    "018": "Robi",
    "016": "Airtel",
    "015": "Teletalk",
}


def clean_bd_number(raw_number: str) -> str:
    """
    Cleans and standardizes any Bangladeshi phone number to international format: +8801XXXXXXXXX
    """
    digits = re.sub(r"\D", "", raw_number)

    # If starts with 880, strip 88 to normalize to 0...
    if digits.startswith("880"):
        digits = digits[2:]
    elif not digits.startswith("0") and len(digits) == 10:
        digits = "0" + digits

    if len(digits) != 11:
        raise ValueError(f"Invalid phone number length ({len(digits)} digits). Must be 11 digits like 01712345678.")

    prefix = digits[:3]
    if prefix not in VALID_PREFIXES:
        raise ValueError(f"Invalid Bangladeshi mobile prefix: {prefix}. Valid prefixes: {', '.join(VALID_PREFIXES.keys())}")

    return f"+88{digits}"


def is_valid_bd_number(raw_number: str) -> Tuple[bool, str]:
    """
    Checks if a number is a valid Bangladeshi number.
    Returns (is_valid, error_message_or_cleaned_number)
    """
    try:
        cleaned = clean_bd_number(raw_number)
        return True, cleaned
    except ValueError as e:
        return False, str(e)


def generate_serial_numbers(start_number: str, count: int) -> List[str]:
    """
    Generates a list of serialized Bangladeshi phone numbers starting from `start_number`.
    Each subsequent number is incremented by 1.
    """
    cleaned = clean_bd_number(start_number)
    base_digits = cleaned.replace("+88", "")  # e.g. "01795664122"
    base_int = int(base_digits)

    numbers: List[str] = []
    for i in range(count):
        current_int = base_int + i
        current_digits = f"{current_int:011d}"
        prefix = current_digits[:3]
        if prefix in VALID_PREFIXES:
            numbers.append(f"+88{current_digits}")
        else:
            # Reached beyond operator range
            break

    return numbers


def get_operator_from_number(number: str) -> str:
    """
    Returns operator name based on prefix.
    """
    digits = re.sub(r"\D", "", number)
    if digits.startswith("880"):
        digits = digits[2:]
    prefix = digits[:3]
    return VALID_PREFIXES.get(prefix, "Unknown")
