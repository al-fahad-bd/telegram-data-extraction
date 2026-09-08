import asyncio
import inspect
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from telethon import TelegramClient
from telethon.tl.types import User

from src.telegram_client import api_hash, api_id

SESSIONS_DIR = Path(__file__).resolve().parent.parent / "sessions"


async def _disconnect_client(client: Optional[TelegramClient]) -> None:
    """Safely disconnects a Telethon client whether disconnect returns an awaitable or None."""
    if client:
        try:
            res = client.disconnect()
            if inspect.isawaitable(res):
                await res
        except Exception:
            pass



class TelegramAccount:
    def __init__(self, session_name: str, session_path: Path) -> None:
        self.session_name = session_name
        self.session_path = session_path
        self.user_id: Optional[int] = None
        self.first_name: str = "User"
        self.username: str = ""
        self.phone: str = ""
        self.is_authorized: bool = False
        self.status: str = "available"  # "active", "available", "rate_limited", "unauthorized"
        self.rate_limited_until: Optional[datetime] = None
        self.limit_message: str = ""

    @property
    def display_name(self) -> str:
        handle = f" (@{self.username})" if self.username else ""
        return f"{self.first_name}{handle}".strip() or self.session_name

    def to_dict(self, is_active: bool = False) -> Dict[str, Any]:
        return {
            "session_name": self.session_name,
            "display_name": self.display_name,
            "username": self.username,
            "first_name": self.first_name,
            "is_authorized": self.is_authorized,
            "status": "active" if is_active else self.status,
            "rate_limited_until": (
                self.rate_limited_until.strftime("%Y-%m-%d %H:%M:%S")
                if self.rate_limited_until
                else None
            ),
            "limit_message": self.limit_message,
        }


class SessionPoolManager:
    """
    Manages multiple Telegram user sessions, tracks rate limits,
    and automatically switches to a healthy account when daily quotas are reached.
    """

    def __init__(self) -> None:
        self.accounts: Dict[str, TelegramAccount] = {}
        self.active_session_name: Optional[str] = None
        self.active_client: Optional[TelegramClient] = None
        self.auto_switch: bool = True
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.scan_sessions()

    def scan_sessions(self) -> List[str]:
        """Scans the sessions/ folder for all *.session files."""
        found_names = []
        for file in SESSIONS_DIR.glob("*.session"):
            name = file.stem
            found_names.append(name)
            if name not in self.accounts:
                self.accounts[name] = TelegramAccount(name, file)
        # Prune removed session files
        for name in list(self.accounts.keys()):
            if name not in found_names:
                del self.accounts[name]
        return found_names

    async def initialize_pool(self) -> Tuple[bool, str]:
        """Discovers sessions and connects to the primary/first available account."""
        self.scan_sessions()
        if not self.accounts:
            # Fallback default
            default_path = SESSIONS_DIR / "telegram.session"
            self.accounts["telegram"] = TelegramAccount("telegram", default_path)

        # Pick first available session
        target_name = self.active_session_name or list(self.accounts.keys())[0]
        return await self.switch_to_account(target_name)

    async def connect_client_for_session(self, session_name: str) -> Tuple[Optional[TelegramClient], Optional[TelegramAccount], str]:
        session_file = SESSIONS_DIR / f"{session_name}.session"
        client = TelegramClient(str(SESSIONS_DIR / session_name), api_id, str(api_hash))
        try:
            await client.connect()
            if not await client.is_user_authorized():
                account = self.accounts.get(session_name) or TelegramAccount(session_name, session_file)
                account.is_authorized = False
                account.status = "unauthorized"
                self.accounts[session_name] = account
                await _disconnect_client(client)
                return None, account, "Session not authorized"

            me = await client.get_me()
            account = self.accounts.get(session_name) or TelegramAccount(session_name, session_file)
            account.is_authorized = True
            account.status = "available"
            if isinstance(me, User):
                account.user_id = me.id
                account.first_name = me.first_name or "User"
                account.username = me.username or ""
                account.phone = me.phone or ""

            self.accounts[session_name] = account
            return client, account, ""
        except Exception as e:
            await _disconnect_client(client)
            return None, None, str(e)

    async def switch_to_account(self, session_name: str) -> Tuple[bool, str]:
        """Switches active Telegram connection to the specified session."""
        if session_name not in self.accounts:
            self.scan_sessions()
            if session_name not in self.accounts:
                return False, f"Session '{session_name}' not found."

        # Disconnect existing client if connected
        if self.active_client:
            try:
                if self.active_client.is_connected():
                    await _disconnect_client(self.active_client)
            except Exception:
                pass
            self.active_client = None

        client, account, err = await self.connect_client_for_session(session_name)
        if not client or not account:
            return False, err or "Failed to connect."

        self.active_client = client
        self.active_session_name = session_name
        account.status = "active"
        return True, f"Connected as {account.display_name}"

    def mark_active_rate_limited(self, reason: str = "") -> None:
        """Marks currently active account as rate-limited with estimated reset time."""
        if not self.active_session_name or self.active_session_name not in self.accounts:
            return

        account = self.accounts[self.active_session_name]
        account.status = "rate_limited"
        account.limit_message = reason

        # Try to parse hours/minutes from message (e.g. "reset in 21 hours 40 minutes")
        hours, minutes = 24, 0
        h_match = re.search(r"(\d+)\s*(?:hours|hour|hr|h)", reason, re.IGNORECASE)
        m_match = re.search(r"(\d+)\s*(?:minutes|minute|min|m)", reason, re.IGNORECASE)
        if h_match:
            hours = int(h_match.group(1))
        if m_match:
            minutes = int(m_match.group(1))

        account.rate_limited_until = datetime.now() + timedelta(hours=hours, minutes=minutes)

    async def switch_to_next_available(self) -> Tuple[bool, str]:
        """
        Finds next authorized, non-rate-limited account in the pool and connects to it.
        """
        self.scan_sessions()

        # Check for expired rate limits
        now = datetime.now()
        for acc in self.accounts.values():
            if acc.status == "rate_limited" and acc.rate_limited_until and now >= acc.rate_limited_until:
                acc.status = "available"
                acc.rate_limited_until = None

        candidates = [
            name for name, acc in self.accounts.items()
            if name != self.active_session_name and acc.status in ("available", "active")
        ]

        if not candidates:
            return False, "No other available Telegram accounts in pool. All accounts are rate-limited or unauthorized."

        next_name = candidates[0]
        return await self.switch_to_account(next_name)

    def get_pool_summary(self) -> List[Dict[str, Any]]:
        self.scan_sessions()
        return [
            acc.to_dict(is_active=(acc.session_name == self.active_session_name))
            for acc in self.accounts.values()
        ]

    def get_active_account_info(self) -> Optional[Dict[str, Any]]:
        if self.active_session_name and self.active_session_name in self.accounts:
            return self.accounts[self.active_session_name].to_dict(is_active=True)
        return None
