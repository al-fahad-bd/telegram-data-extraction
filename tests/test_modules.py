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
    assert parsed["has_whatsapp"] is True
    assert parsed["has_telegram"] is True

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


if __name__ == "__main__":
    test_generator()
    test_parser()
    print("All generator & parser tests passed successfully!")
