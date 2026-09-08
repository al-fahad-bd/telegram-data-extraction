import os
import sys

# Silence macOS Tk deprecation warning
os.environ["TK_SILENCE_DEPRECATION"] = "1"

from src.gui_app import launch_gui
from src.web_gui import launch_web_gui


def main() -> None:
    if "--cli" in sys.argv:
        # Launch terminal CLI mode if explicitly requested
        import asyncio
        from telethon.tl.types import User

        from src.bot_handler import send_to_bot
        from src.telegram_client import client

        async def interactive_cli() -> None:
            me = await client.get_me()
            assert isinstance(me, User)
            print("Connected successfully!")
            print(f"Name: {me.first_name}")
            print(f"Username: @{me.username}")
            print("\nTelegram client is ready. Type a phone number or 'exit' to quit.")

            while True:
                try:
                    user_input = await asyncio.to_thread(input, "Send to bot > ")
                except (EOFError, KeyboardInterrupt):
                    break

                q = user_input.strip()
                if not q:
                    continue
                if q.lower() in ("exit", "quit", "q"):
                    break

                await send_to_bot(client, "TrueCalleRobot", q)

        with client:
            try:
                client.loop.run_until_complete(interactive_cli())
            except KeyboardInterrupt:
                print("\nExited.")
    elif "--add-account" in sys.argv:
        # Interactive CLI login to add another Telegram account to the pool
        import asyncio
        from telethon import TelegramClient
        from telethon.tl.types import User
        from src.telegram_client import api_id, api_hash
        from pathlib import Path

        idx = sys.argv.index("--add-account")
        name = sys.argv[idx + 1] if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-") else ""
        if not name:
            name = input("Enter session name (e.g. account2, work_tg): ").strip()
        if not name:
            name = "account2"

        session_path = Path("sessions") / f"{name}.session"
        print(f"\n🔐 Authenticating new Telegram session: '{name}'")
        print(f"Target path: {session_path}\n")

        import inspect
        from src.session_manager import _disconnect_client

        async def login():
            client = TelegramClient(str(Path("sessions") / name), api_id, str(api_hash))
            start_coro = client.start()
            if inspect.isawaitable(start_coro):
                await start_coro
            me = await client.get_me()
            if isinstance(me, User):
                uname = f"@{me.username}" if me.username else ""
                print(f"\n🎉 Successfully authenticated!")
                print(f"Name: {me.first_name}")
                print(f"Username: {uname}")
                print(f"Phone: {me.phone}")
                print(f"Session saved as: sessions/{name}.session")
                print(f"This account is now available in your Session Pool for automatic rotation!")
            await _disconnect_client(client)

        asyncio.run(login())
    elif "--list-accounts" in sys.argv:
        from src.session_manager import SessionPoolManager
        pool = SessionPoolManager()
        print("\n📋 Telegram Session Pool:")
        for acc in pool.get_pool_summary():
            status_icon = "🟢" if acc["status"] in ("active", "available") else "🔴"
            print(f"  {status_icon} [{acc['session_name']}] {acc['display_name']} - Status: {acc['status'].upper()}")
        print("")
    elif "--tk" in sys.argv:
        # Launch classic Tkinter Desktop GUI (with macOS Cocoa refresh fix)
        launch_gui()
    else:
        # Default: Launch Modern, Glassmorphic Desktop GUI
        launch_web_gui()


if __name__ == "__main__":
    main()