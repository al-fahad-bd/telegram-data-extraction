import os

from dotenv import load_dotenv
from telethon import TelegramClient


load_dotenv()

api_id_env = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")

if not api_id_env or not api_hash:
    raise ValueError(
        "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in your .env or environment variables."
    )

assert api_hash is not None
api_id = int(api_id_env)

client = TelegramClient(
    "sessions/telegram",
    api_id,
    api_hash,
)