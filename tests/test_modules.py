import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.generator import clean_bd_number, generate_serial_numbers, is_valid_bd_number
from src.parser import parse_bot_response


def test_generator():
    valid, num = is_valid_bd_number("01795664120")
    assert valid and num == "+8801795664120", num

    valid, num = is_valid_bd_number("+8801795664120")
    assert valid and num == "+8801795664120", num

    serials = generate_serial_numbers("01795664120", 5)
    assert len(serials) == 5
    assert serials[0] == "+8801795664120"
    assert serials[1] == "+8801795664121"
    assert serials[2] == "+8801795664122"
    assert serials[3] == "+8801795664123"
    assert serials[4] == "+8801795664124"


def test_parser():
    sample = (
        "**Number: ****+8801795664122**\n"
        "**Country: Bangladesh** 🇧🇩\n\n"
        "**🔍**** TrueCaller Says:**\n\n"
        "**Carrier:** `Grameenphone`\n\n"
        "**🔍**** Unknown Says:**\n\n"
        "**Name:** `Shiam Cpi Dpi`\n\n"
        "💻[WhatsApp](https://wa.me/+8801795664122) | [Telegram](https://t.me/+8801795664122)✈️"
    )
    parsed = parse_bot_response(sample, "+8801795664122")
    assert parsed["name"] == "Shiam Cpi Dpi", f"Expected Shiam Cpi Dpi, got {parsed['name']}"
    assert parsed["carrier"] == "Grameenphone", f"Expected Grameenphone, got {parsed['carrier']}"
    assert parsed["country"] == "Bangladesh", f"Expected Bangladesh, got {parsed['country']}"
    assert parsed["status"] == "Found", f"Expected Found, got {parsed['status']}"
    assert parsed["has_whatsapp"] is False
    assert parsed["has_telegram"] is False

    # Test Not Found
    sample_not_found = (
        "**Number: ****+8801644234865**\n"
        "**Country: Bangladesh** 🇧🇩\n\n"
        "**🔍**** TrueCaller Says:**\n\n"
        "**Carrier:** `Robi`\n\n"
        "**🔍**** Unknown Says:**\n\n"
        "**Name:** `Not Found`\n\n"
        "💻[WhatsApp](https://wa.me/+8801644234865) | [Telegram](https://t.me/+8801644234865)✈️"
    )
    parsed_nf = parse_bot_response(sample_not_found, "+8801644234865")
    assert parsed_nf["name"] == "Not Found"
    assert parsed_nf["carrier"] == "Robi"
    assert parsed_nf["status"] == "Not Found"


def test_global_generator():
    from src.generator import clean_phone_number, is_valid_phone_number

    # US Number
    valid, num = is_valid_phone_number("+12025550120")
    assert valid and num == "+12025550120", num

    us_serials = generate_serial_numbers("+12025550120", 3)
    assert len(us_serials) == 3
    assert us_serials == ["+12025550120", "+12025550121", "+12025550122"]

    # UK Number
    valid, num = is_valid_phone_number("+447911123450")
    assert valid and num == "+447911123450", num
    uk_serials = generate_serial_numbers("+447911123450", 2)
    assert uk_serials == ["+447911123450", "+447911123451"]

    # India Number
    in_serials = generate_serial_numbers("+919876543210", 3)
    assert in_serials == ["+919876543210", "+919876543211", "+919876543212"]

    # UAE Number
    ae_serials = generate_serial_numbers("+971501234567", 2)
    assert ae_serials == ["+971501234567", "+971501234568"]


if __name__ == "__main__":
    test_generator()
    test_global_generator()
    test_parser()
    print("All generator, parser & global country tests passed successfully!")
