import asyncio

from telethon import TelegramClient
from telethon.errors import FloodWaitError


async def send_to_bot(
    client: TelegramClient,
    bot_username: str,
    message: str,
    timeout: int = 30,
):
    try:
        print(f"Sending message to {bot_username}...")

        async with client.conversation(
            bot_username,
            timeout=timeout,
        ) as conv:

            await conv.send_message(message)

            print("Message sent successfully.")
            print("Waiting for bot response...")

            response = await conv.get_response()

            # The Truecaller bot initially sends a "Searching..." placeholder,
            # then EDITS that message with the full details within 1-2 seconds.
            if response.text and "searching" in response.text.lower():
                print("Bot is searching, waiting for result...")
                try:
                    # In Telethon, calling get_edit() without arguments awaits the edit
                    # to the message that responded to our last sent message.
                    edited_response = await conv.get_edit(timeout=10)
                    if edited_response and edited_response.text:
                        response = edited_response
                except (asyncio.TimeoutError, TimeoutError):
                    print("Timed out waiting for bot to edit its response.")

            if response.text:
                print("\nBot response:")
                print(response.text)

                return response.text

            print("\nBot responded, but there was no text.")

            return None

    except FloodWaitError as e:
        print(
            f"\nTelegram rate limit reached."
            f"\nPlease wait {e.seconds} seconds before trying again."
        )

        return None

    except (asyncio.TimeoutError, TimeoutError):
        print(
            f"\nNo response received from {bot_username}"
            f" within {timeout} seconds."
        )

        return None