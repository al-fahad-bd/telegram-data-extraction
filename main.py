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
    elif "--tk" in sys.argv:
        # Launch classic Tkinter Desktop GUI (with macOS Cocoa refresh fix)
        launch_gui()
    else:
        # Default: Launch Modern, Glassmorphic Desktop GUI
        launch_web_gui()


if __name__ == "__main__":
    main()