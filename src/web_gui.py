import asyncio
import csv
import io
import os
import random
import re
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telethon import TelegramClient, errors, utils
from telethon.tl.functions.contacts import ResolvePhoneRequest
from telethon.tl.types import User

from src.bot_handler import send_to_bot
from src.generator import GLOBAL_COUNTRY_CODES, generate_serial_numbers, is_valid_phone_number
from src.parser import parse_bot_response
from src.session_manager import SESSIONS_DIR, SessionPoolManager, _disconnect_client
from src.telegram_client import api_hash, api_id

BOT_USERNAME = "TrueCalleRobot"
STATIC_DIR = Path(__file__).resolve().parent / "static"


async def verify_telegram_registered(client: Optional[TelegramClient], phone: str) -> bool:
    """
    Directly checks Telegram servers via MTProto whether a phone number has an active Telegram account.
    Returns True if registered, False otherwise.
    """
    if not client:
        return False
    try:
        clean = re.sub(r"[^\d]", "", phone)
        res = await client(ResolvePhoneRequest(clean))
        users = getattr(res, "users", None)
        return bool(users and len(users) > 0)
    except errors.PhoneNotOccupiedError:
        return False
    except Exception:
        return False


class ConnectionManager:
    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)

    async def broadcast(self, msg_type: str, payload: Any) -> None:
        if not self.active_connections:
            return
        message = {"type": msg_type, "payload": payload}
        disconnected = set()
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.add(ws)
        for dead in disconnected:
            self.active_connections.discard(dead)


ws_manager = ConnectionManager()


class StartBatchRequest(BaseModel):
    start_number: str
    count: int = 20
    min_delay: int = 20
    max_delay: int = 30


class LookupRequest(BaseModel):
    phone_number: str


class SwitchAccountRequest(BaseModel):
    session_name: str


class RequestCodeRequest(BaseModel):
    session_name: str
    phone_number: str


class VerifyCodeRequest(BaseModel):
    session_name: str
    code: str
    password: Optional[str] = None


class CancelAuthRequest(BaseModel):
    session_name: str


class ExtractorEngine:
    def __init__(self) -> None:
        self.pool_manager = SessionPoolManager()
        self.tg_client: Optional[TelegramClient] = None
        self.is_connected = False
        self.user_display = ""
        self.connection_error = ""

        # Automation state
        self.is_running = False
        self.is_paused = False
        self.current_target = ""
        self.stop_requested = False
        self.batch_task: Optional[asyncio.Task] = None

        # Extracted Records
        self.records: List[Dict[str, Any]] = []

    async def init_telegram(self) -> None:
        try:
            await ws_manager.broadcast(
                "log",
                {"message": "Scanning and initializing Telegram session pool...", "level": "info"},
            )
            success, msg = await self.pool_manager.initialize_pool()
            if success and self.pool_manager.active_client:
                self.tg_client = self.pool_manager.active_client
                self.is_connected = True
                self.connection_error = ""
                acc_info = self.pool_manager.get_active_account_info()
                self.user_display = acc_info["display_name"] if acc_info else "Telegram User"
                await self.broadcast_tg_status()
                await ws_manager.broadcast(
                    "log",
                    {
                        "message": f"Active session: '{self.pool_manager.active_session_name}' ({self.user_display})",
                        "level": "success",
                    },
                )
            else:
                self.is_connected = False
                self.connection_error = msg or "Session not authorized. Run CLI or --add-account to log in."
                await self.broadcast_tg_status()
                await ws_manager.broadcast(
                    "log",
                    {"message": f"Telegram session setup: {self.connection_error}", "level": "warning"},
                )
        except Exception as e:
            self.is_connected = False
            self.connection_error = str(e)
            await self.broadcast_tg_status()
            await ws_manager.broadcast(
                "log",
                {"message": f"Telegram connection error: {e}", "level": "error"},
            )

    async def broadcast_tg_status(self) -> None:
        await ws_manager.broadcast(
            "tg_status",
            {
                "connected": self.is_connected,
                "user_display": self.user_display,
                "error": self.connection_error,
                "active_session": self.pool_manager.active_session_name,
                "accounts_pool": self.pool_manager.get_pool_summary(),
                "auto_switch": self.pool_manager.auto_switch,
            },
        )

    def calculate_metrics(self) -> Dict[str, Any]:
        total = len(self.records)
        found = sum(1 for r in self.records if (r.get("status") or "").lower() == "found")
        not_found = sum(1 for r in self.records if (r.get("status") or "").lower() == "not found")
        rate = round((found / total * 100), 1) if total > 0 else 0
        return {
            "total": total,
            "found": found,
            "not_found": not_found,
            "rate": rate,
        }

    async def broadcast_metrics(self) -> None:
        metrics = self.calculate_metrics()
        await ws_manager.broadcast("metrics", metrics)

    async def broadcast_automation_state(self) -> None:
        await ws_manager.broadcast(
            "automation_state",
            {
                "running": self.is_running,
                "paused": self.is_paused,
            },
        )

    async def single_lookup(self, phone: str) -> Dict[str, Any]:
        if not self.is_connected or not self.tg_client:
            raise HTTPException(status_code=400, detail="Telegram client is not connected.")

        valid, cleaned = is_valid_phone_number(phone)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid phone number: {cleaned}")

        await ws_manager.broadcast(
            "log",
            {"message": f"Executing single lookup for {cleaned}...", "level": "info"},
        )
        await ws_manager.broadcast("target_number", {"phone_number": cleaned})

        raw_response = await send_to_bot(self.tg_client, BOT_USERNAME, cleaned)
        parsed = parse_bot_response(raw_response, cleaned)

        is_found = (parsed.get("status") == "Found")
        has_tg = False
        if is_found:
            has_tg = await verify_telegram_registered(self.tg_client, cleaned)

        record = {
            "id": len(self.records) + 1,
            "time": datetime.now().strftime("%H:%M:%S"),
            "phone_number": cleaned,
            "name": parsed.get("name", "Not Found"),
            "carrier": parsed.get("carrier", "Unknown"),
            "country": parsed.get("country", "Unknown"),
            "has_whatsapp": is_found,
            "has_telegram": has_tg,
            "status": parsed.get("status", "Unknown"),
            "timestamp": parsed.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "raw_text": parsed.get("raw_text", ""),
        }

        self.records.append(record)
        await ws_manager.broadcast("new_record", record)
        await self.broadcast_metrics()

        log_level = "success" if record["status"] == "Found" else "info"
        await ws_manager.broadcast(
            "log",
            {
                "message": f"Result for {cleaned}: {record['name']} [{record['carrier']}] ({record['status']})",
                "level": log_level,
            },
        )
        await ws_manager.broadcast("target_number", {"phone_number": "Lookup Complete"})
        return record

    async def start_batch(
        self,
        start_number: str,
        count: int,
        min_delay: int,
        max_delay: int,
    ) -> None:
        if self.is_running:
            raise HTTPException(status_code=400, detail="Automation is already running.")
        if not self.is_connected or not self.tg_client:
            raise HTTPException(status_code=400, detail="Telegram is not connected.")

        valid, cleaned = is_valid_phone_number(start_number)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Invalid start number: {cleaned}")

        numbers = generate_serial_numbers(cleaned, count)
        if not numbers:
            raise HTTPException(status_code=400, detail="No numbers generated from given input.")

        self.is_running = True
        self.is_paused = False
        self.stop_requested = False
        await self.broadcast_automation_state()

        await ws_manager.broadcast(
            "log",
            {
                "message": f"Starting automated batch: {len(numbers)} numbers generated from {cleaned}",
                "level": "info",
            },
        )

        self.batch_task = asyncio.create_task(
            self._run_batch_loop(numbers, min_delay, max_delay)
        )

    async def _run_batch_loop(
        self,
        numbers: List[str],
        min_delay: int,
        max_delay: int,
    ) -> None:
        total = len(numbers)
        try:
            for idx, phone in enumerate(numbers):
                if self.stop_requested:
                    await ws_manager.broadcast(
                        "log",
                        {"message": "Automation stopped by user.", "level": "warning"},
                    )
                    break

                # Handle Pause loop
                while self.is_paused:
                    if self.stop_requested:
                        break
                    await asyncio.sleep(0.5)

                if self.stop_requested:
                    break

                current_index = idx + 1
                percent = round((current_index / total) * 100)
                await ws_manager.broadcast(
                    "progress",
                    {"current": current_index, "total": total, "percent": percent},
                )
                await ws_manager.broadcast("target_number", {"phone_number": phone})
                await ws_manager.broadcast(
                    "log",
                    {"message": f"[{current_index}/{total}] Querying {phone}...", "level": "info"},
                )

                assert self.tg_client is not None
                raw = await send_to_bot(self.tg_client, BOT_USERNAME, phone)
                parsed = parse_bot_response(raw, phone)

                is_found = (parsed.get("status") == "Found")
                has_tg = False
                if is_found:
                    has_tg = await verify_telegram_registered(self.tg_client, phone)

                record = {
                    "id": len(self.records) + 1,
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "phone_number": phone,
                    "name": parsed.get("name", "Not Found"),
                    "carrier": parsed.get("carrier", "Unknown"),
                    "country": parsed.get("country", "Unknown"),
                    "has_whatsapp": is_found,
                    "has_telegram": has_tg,
                    "status": parsed.get("status", "Unknown"),
                    "timestamp": parsed.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    "raw_text": parsed.get("raw_text", ""),
                }

                self.records.append(record)
                await ws_manager.broadcast("new_record", record)
                await self.broadcast_metrics()

                log_level = "success" if record["status"] == "Found" else ("error" if record["status"] == "Rate Limited" else "info")
                await ws_manager.broadcast(
                    "log",
                    {
                        "message": f"[{current_index}/{total}] Extracted: {record['name']} | {record['carrier']} ({record['status']})",
                        "level": log_level,
                    },
                )

                # If bot daily limit reached, check if we can auto-switch to another account!
                if record["status"] == "Rate Limited":
                    raw_limit_msg = record.get("raw_text", "")
                    self.pool_manager.mark_active_rate_limited(raw_limit_msg)
                    if self.pool_manager.auto_switch:
                        await ws_manager.broadcast(
                            "log",
                            {
                                "message": f"⚠️ Daily limit reached on '{self.pool_manager.active_session_name}'. Auto-switching to next Telegram account...",
                                "level": "warning",
                            },
                        )
                        switched, switch_msg = await self.pool_manager.switch_to_next_available()
                        if switched and self.pool_manager.active_client:
                            self.tg_client = self.pool_manager.active_client
                            acc = self.pool_manager.get_active_account_info()
                            self.user_display = acc["display_name"] if acc else "Telegram User"
                            await self.broadcast_tg_status()
                            await ws_manager.broadcast(
                                "log",
                                {
                                    "message": f"🔄 Switched to '{self.pool_manager.active_session_name}' ({self.user_display}). Retrying query for {phone}...",
                                    "level": "success",
                                },
                            )
                            # Retry this exact phone number with the new account
                            retry_raw = await send_to_bot(self.tg_client, BOT_USERNAME, phone)
                            retry_parsed = parse_bot_response(retry_raw, phone)
                            is_retry_found = (retry_parsed.get("status") == "Found")
                            has_retry_tg = False
                            if is_retry_found:
                                has_retry_tg = await verify_telegram_registered(self.tg_client, phone)
                            record.update({
                                "name": retry_parsed.get("name", "Not Found"),
                                "carrier": retry_parsed.get("carrier", "Unknown"),
                                "country": retry_parsed.get("country", "Unknown"),
                                "has_whatsapp": is_retry_found,
                                "has_telegram": has_retry_tg,
                                "status": retry_parsed.get("status", "Unknown"),
                                "raw_text": retry_parsed.get("raw_text", ""),
                            })
                            await ws_manager.broadcast("new_record", record)
                            await self.broadcast_metrics()
                            log_level = "success" if record["status"] == "Found" else "info"
                            await ws_manager.broadcast(
                                "log",
                                {
                                    "message": f"[{current_index}/{total}] Retry result: {record['name']} | {record['carrier']} ({record['status']})",
                                    "level": log_level,
                                },
                            )
                        else:
                            await ws_manager.broadcast(
                                "log",
                                {
                                    "message": f"❌ {switch_msg}. Pausing automation.",
                                    "level": "error",
                                },
                            )
                            self.is_paused = True
                            await self.broadcast_automation_state()
                    else:
                        await ws_manager.broadcast(
                            "log",
                            {
                                "message": "⚠️ Daily search limit reached. Auto-switch is disabled. Pausing batch.",
                                "level": "warning",
                            },
                        )
                        self.is_paused = True
                        await self.broadcast_automation_state()

                # Delay before next query if not last
                if current_index < total and not self.stop_requested:
                    delay = random.uniform(min_delay, max_delay)
                    remaining = int(delay)
                    await ws_manager.broadcast(
                        "log",
                        {
                            "message": f"Antiflood delay: waiting {remaining}s before next query...",
                            "level": "info",
                        },
                    )
                    while remaining > 0 and not self.stop_requested:
                        await ws_manager.broadcast("countdown", {"seconds": remaining})
                        while self.is_paused and not self.stop_requested:
                            await asyncio.sleep(0.5)
                        await asyncio.sleep(1)
                        remaining -= 1
                    await ws_manager.broadcast("countdown", {"seconds": 0})

            await ws_manager.broadcast(
                "log",
                {"message": "Automated extraction batch completed!", "level": "success"},
            )
            await ws_manager.broadcast("target_number", {"phone_number": "Batch Finished"})
        except Exception as e:
            await ws_manager.broadcast(
                "log",
                {"message": f"Error during batch execution: {e}", "level": "error"},
            )
        finally:
            self.is_running = False
            self.is_paused = False
            await self.broadcast_automation_state()

    def pause_batch(self) -> None:
        if self.is_running:
            self.is_paused = not self.is_paused

    def stop_batch(self) -> None:
        if self.is_running:
            self.stop_requested = True
            self.is_paused = False

    def clear_records(self) -> None:
        self.records.clear()


engine = ExtractorEngine()
app = FastAPI(title="Truecaller BD Extractor Desktop")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(engine.init_telegram())


@app.get("/", response_class=HTMLResponse)
async def get_index() -> HTMLResponse:
    index_file = STATIC_DIR / "index.html"
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        # Initial sync
        await websocket.send_json(
            {
                "type": "tg_status",
                "payload": {
                    "connected": engine.is_connected,
                    "user_display": engine.user_display,
                    "error": engine.connection_error,
                },
            }
        )
        await websocket.send_json(
            {
                "type": "automation_state",
                "payload": {
                    "running": engine.is_running,
                    "paused": engine.is_paused,
                },
            }
        )
        await websocket.send_json(
            {"type": "metrics", "payload": engine.calculate_metrics()}
        )
        await websocket.send_json(
            {"type": "records_sync", "payload": {"records": engine.records}}
        )

        while True:
            # Keep-alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@app.post("/api/start")
async def api_start(req: StartBatchRequest) -> Dict[str, str]:
    await engine.start_batch(
        start_number=req.start_number,
        count=req.count,
        min_delay=req.min_delay,
        max_delay=req.max_delay,
    )
    return {"status": "started"}


@app.post("/api/pause")
async def api_pause() -> Dict[str, Any]:
    engine.pause_batch()
    await engine.broadcast_automation_state()
    return {"status": "toggled", "is_paused": engine.is_paused}


@app.post("/api/stop")
async def api_stop() -> Dict[str, str]:
    engine.stop_batch()
    await engine.broadcast_automation_state()
    return {"status": "stopping"}


@app.post("/api/lookup")
async def api_lookup(req: LookupRequest) -> Dict[str, Any]:
    return await engine.single_lookup(req.phone_number)


@app.post("/api/clear")
async def api_clear() -> Dict[str, str]:
    if engine.is_running:
        raise HTTPException(status_code=400, detail="Cannot clear while automation is running.")
    engine.clear_records()
    await ws_manager.broadcast("clear_table", {})
    await engine.broadcast_metrics()
    return {"status": "cleared"}


@app.get("/api/accounts")
async def api_get_accounts() -> Dict[str, Any]:
    return {
        "active": engine.pool_manager.active_session_name,
        "auto_switch": engine.pool_manager.auto_switch,
        "accounts": engine.pool_manager.get_pool_summary(),
    }


@app.post("/api/accounts/switch")
async def api_switch_account(req: SwitchAccountRequest) -> Dict[str, Any]:
    if engine.is_running and not engine.is_paused:
        raise HTTPException(status_code=400, detail="Please pause automation before manually switching accounts.")
    success, msg = await engine.pool_manager.switch_to_account(req.session_name)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    engine.tg_client = engine.pool_manager.active_client
    engine.is_connected = True
    acc = engine.pool_manager.get_active_account_info()
    engine.user_display = acc["display_name"] if acc else "Telegram User"
    await engine.broadcast_tg_status()
    await ws_manager.broadcast(
        "log",
        {
            "message": f"Switched active Telegram account to '{req.session_name}' ({engine.user_display})",
            "level": "info",
        },
    )
    return {"status": "switched", "session_name": req.session_name, "user_display": engine.user_display}


@app.post("/api/accounts/toggle-auto-switch")
async def api_toggle_auto_switch() -> Dict[str, Any]:
    engine.pool_manager.auto_switch = not engine.pool_manager.auto_switch
    await engine.broadcast_tg_status()
    await ws_manager.broadcast(
        "log",
        {
            "message": f"Auto-switch on daily limit set to: {'ENABLED' if engine.pool_manager.auto_switch else 'DISABLED'}",
            "level": "info",
        },
    )
    return {"auto_switch": engine.pool_manager.auto_switch}


pending_auth_sessions: Dict[str, Dict[str, Any]] = {}


@app.post("/api/accounts/request-code")
async def api_request_code(req: RequestCodeRequest) -> Dict[str, Any]:
    s_name = re.sub(r"[^a-zA-Z0-9_\-]", "", req.session_name.strip())
    if not s_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid session name. Use alphanumeric characters and underscores.",
        )

    phone = req.phone_number.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    parsed_digits = utils.parse_phone(phone)
    if not parsed_digits or len(parsed_digits) < 7:
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number format. Please provide a valid international number with country code (e.g. +88017...).",
        )

    # Clean up existing in-flight pending session for this name if any
    if s_name in pending_auth_sessions:
        old_client = pending_auth_sessions[s_name].get("client")
        if old_client:
            await _disconnect_client(old_client)
        del pending_auth_sessions[s_name]

    session_file_path = SESSIONS_DIR / s_name
    client = TelegramClient(str(session_file_path), api_id, str(api_hash))

    try:
        await client.connect()
        sent_code = await client.send_code_request(phone)
        phone_code_hash = sent_code.phone_code_hash

        pending_auth_sessions[s_name] = {
            "client": client,
            "phone": phone,
            "phone_code_hash": phone_code_hash,
            "session_name": s_name,
            "created_at": datetime.now(),
        }

        return {
            "status": "code_sent",
            "session_name": s_name,
            "phone": phone,
            "message": f"Verification code sent to {phone} via Telegram app / SMS.",
        }
    except errors.PhoneNumberInvalidError:
        await _disconnect_client(client)
        raise HTTPException(
            status_code=400,
            detail="The phone number entered is invalid or not registered on Telegram.",
        )
    except errors.FloodWaitError as e:
        await _disconnect_client(client)
        raise HTTPException(
            status_code=429,
            detail=f"Telegram FloodWait: please wait {e.seconds} seconds before requesting another code.",
        )
    except Exception as e:
        await _disconnect_client(client)
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/accounts/verify-code")
async def api_verify_code(req: VerifyCodeRequest) -> Dict[str, Any]:
    s_name = re.sub(r"[^a-zA-Z0-9_\-]", "", req.session_name.strip())
    if s_name not in pending_auth_sessions:
        raise HTTPException(
            status_code=400,
            detail="Verification session expired or not found. Please request a new code.",
        )

    pending = pending_auth_sessions[s_name]
    client: TelegramClient = pending["client"]
    phone: str = pending["phone"]
    phone_code_hash: str = pending["phone_code_hash"]

    try:
        if req.password:
            # Complete 2-Step Verification password login
            await client.sign_in(password=req.password)
        else:
            code = req.code.strip().replace(" ", "").replace("-", "")
            await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)

        # Successfully logged in!
        me = await client.get_me()
        user_name = "Telegram User"
        username = ""
        user_phone = phone
        if isinstance(me, User):
            first = me.first_name or ""
            last = me.last_name or ""
            user_name = f"{first} {last}".strip() or "Telegram User"
            username = me.username or ""
            user_phone = me.phone or phone

        # Safely disconnect this client instance so the pool can load and manage the file
        await _disconnect_client(client)
        if s_name in pending_auth_sessions:
            del pending_auth_sessions[s_name]

        # Scan sessions folder to register newly saved session
        engine.pool_manager.scan_sessions()
        await engine.broadcast_tg_status()
        await ws_manager.broadcast(
            "log",
            {
                "message": f"🎉 Successfully connected new Telegram account: '{s_name}' ({user_name})!",
                "level": "success",
            },
        )

        return {
            "status": "success",
            "session_name": s_name,
            "user": {
                "name": user_name,
                "username": f"@{username}" if username else "",
                "phone": user_phone,
            },
            "message": f"Account '{user_name}' successfully connected to your session pool!",
        }
    except errors.SessionPasswordNeededError:
        return {
            "status": "password_needed",
            "session_name": s_name,
            "message": "Two-Step Verification (2FA) is enabled on this account. Please enter your 2FA password.",
        }
    except errors.PasswordHashInvalidError:
        raise HTTPException(status_code=400, detail="Invalid 2FA password. Please check and try again.")
    except errors.PhoneCodeInvalidError:
        raise HTTPException(
            status_code=400,
            detail="Invalid Telegram verification code. Please check your Telegram app and try again.",
        )
    except errors.PhoneCodeExpiredError:
        await _disconnect_client(client)
        if s_name in pending_auth_sessions:
            del pending_auth_sessions[s_name]
        raise HTTPException(
            status_code=400,
            detail="Verification code has expired. Please request a new code.",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/accounts/cancel-auth")
async def api_cancel_auth(req: CancelAuthRequest) -> Dict[str, str]:
    s_name = re.sub(r"[^a-zA-Z0-9_\-]", "", req.session_name.strip())
    if s_name in pending_auth_sessions:
        client = pending_auth_sessions[s_name].get("client")
        if client:
            await _disconnect_client(client)
        del pending_auth_sessions[s_name]
    return {"status": "cancelled"}


@app.get("/api/export")
async def api_export() -> StreamingResponse:
    if not engine.records:
        raise HTTPException(status_code=400, detail="No records to export.")

    output = io.StringIO()
    fieldnames = [
        "phone_number",
        "name",
        "carrier",
        "country",
        "has_whatsapp",
        "has_telegram",
        "status",
        "timestamp",
        "raw_text",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in engine.records:
        writer.writerow({k: row.get(k, "") for k in fieldnames})

    output.seek(0)
    filename = f"truecaller_bd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def open_desktop_window(url: str) -> None:
    """
    Launches Chrome in native application window mode (--app) for a distraction-free
    native desktop app feel, or falls back to system browser.
    """
    chrome_app = "/Applications/Google Chrome.app"
    if os.path.exists(chrome_app):
        try:
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", f"--app={url}"])
            return
        except Exception:
            pass
    webbrowser.open(url)


def launch_web_gui(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f"⚡ Truecaller BD Serialized Extractor GUI")
    print(f"🚀 Running at: {url}")
    print(f"🖥 Dedicated Desktop Window launching...")
    print(f"=======================================================\n")

    # Launch desktop app window after 700ms to allow server to bind
    async def _open_after_delay() -> None:
        await asyncio.sleep(0.7)
        open_desktop_window(url)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    threading_task = asyncio.ensure_future(_open_after_delay(), loop=loop)

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())


if __name__ == "__main__":
    launch_web_gui()
