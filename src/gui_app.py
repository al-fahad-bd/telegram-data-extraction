import asyncio
import csv
import math
import os
import random
import re
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from telethon import TelegramClient
from telethon.tl.types import User

from src.bot_handler import send_to_bot
from src.generator import clean_phone_number, generate_serial_numbers, is_valid_phone_number
from src.parser import parse_bot_response
from src.telegram_client import api_id, api_hash

BOT_USERNAME = "TrueCalleRobot"

# Color Palette (Dark Cyber-Slate Theme)
BG_MAIN = "#0b0f19"         # Deep Navy-Black
BG_CARD = "#111827"         # Dark Slate Card
BG_CARD_ALT = "#1e293b"     # Elevated Slate
BG_INPUT = "#0f172a"        # Deep Input Box
BORDER_COLOR = "#334155"    # Subtle Slate Border
TEXT_PRIMARY = "#f8fafc"    # Bright White
TEXT_MUTED = "#94a3b8"      # Soft Gray
ACCENT_CYAN = "#06b6d4"     # Neon Cyan
ACCENT_GREEN = "#10b981"    # Emerald Green
ACCENT_AMBER = "#f59e0b"    # Amber Warning
ACCENT_ROSE = "#ef4444"     # Soft Rose
ACCENT_INDIGO = "#6366f1"   # Vibrant Indigo
ACCENT_PURPLE = "#a855f7"   # Royal Purple


class ModernCanvasButton(tk.Canvas):
    """Custom pill button with smooth rounded corners, hover glow, and active click animation."""
    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        width: int = 150,
        height: int = 38,
        bg_color: str = ACCENT_GREEN,
        hover_color: str = "#059669",
        active_color: str = "#047857",
        disabled_bg: str = "#334155",
        text_color: str = "#ffffff",
        font: tuple = ("Helvetica", 11, "bold"),
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent.cget("bg"),
            highlightthickness=0,
            cursor="hand2",
        )
        self.btn_text = text
        self.command = command
        self.btn_width = width
        self.btn_height = height
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.active_color = active_color
        self.disabled_bg = disabled_bg
        self.text_color = text_color
        self.btn_font = font
        self.state_enabled = True
        self.is_hovered = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

        self._draw(self.bg_color)

    def _draw(self, fill_color: str, offset: int = 0) -> None:
        self.delete("all")
        radius = self.btn_height // 2
        w = self.btn_width
        h = self.btn_height

        color = fill_color if self.state_enabled else self.disabled_bg
        fg = self.text_color if self.state_enabled else "#64748b"

        # Rounded pill shape
        points = [
            radius, 1 + offset,
            w - radius, 1 + offset,
            w - 1, 1 + offset,
            w - 1, radius + offset,
            w - 1, h - radius + offset,
            w - 1, h - 1 + offset,
            w - radius, h - 1 + offset,
            radius, h - 1 + offset,
            1, h - 1 + offset,
            1, h - radius + offset,
            1, radius + offset,
            1, 1 + offset,
        ]
        self.create_polygon(points, fill=color, smooth=True, outline="")
        self.create_text(
            w // 2,
            (h // 2) + offset,
            text=self.btn_text,
            fill=fg,
            font=self.btn_font,
        )

    def _on_enter(self, event: Any) -> None:
        if self.state_enabled:
            self.is_hovered = True
            self._draw(self.hover_color)

    def _on_leave(self, event: Any) -> None:
        if self.state_enabled:
            self.is_hovered = False
            self._draw(self.bg_color)

    def _on_press(self, event: Any) -> None:
        if self.state_enabled:
            self._draw(self.active_color, offset=1)

    def _on_release(self, event: Any) -> None:
        if self.state_enabled:
            current_color = self.hover_color if self.is_hovered else self.bg_color
            self._draw(current_color, offset=0)
            if self.command:
                self.command()

    def set_text(self, new_text: str) -> None:
        self.btn_text = new_text
        current_color = self.hover_color if self.is_hovered else self.bg_color
        self._draw(current_color)

    def set_colors(self, bg_color: str, hover_color: str, active_color: str) -> None:
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.active_color = active_color
        self._draw(self.bg_color)

    def set_state(self, enabled: bool) -> None:
        self.state_enabled = enabled
        self.config(cursor="hand2" if enabled else "arrow")
        self._draw(self.bg_color)


class TruecallerExtractorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("⚡ Truecaller BD Serialized Extractor")
        self.geometry("1100x780")
        self.minsize(980, 680)
        self.config(bg=BG_MAIN)

        # Automation control state
        self.is_running = False
        self.is_paused = False
        self.results_data: List[Dict[str, Any]] = []
        self.tg_client: Optional[TelegramClient] = None

        # Animation state
        self.pulse_phase = 0
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.anim_job_id: Optional[str] = None

        # Background asyncio loop
        self.loop = asyncio.new_event_loop()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()

        # Window close protocol
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Build UI
        self._build_ui()

        # Fix macOS Sonoma/Sequoia Cocoa blank window rendering issue
        self.after(50, self._force_macos_render)
        self.after(200, self._force_macos_render)

        # Start continuous UI animation loop
        self._start_ui_animation()

        # Connect to Telegram in background
        self._log("Connecting to Telegram in background thread...", tag="info")
        asyncio.run_coroutine_threadsafe(self._init_telegram(), self.loop)

    def _force_macos_render(self) -> None:
        """Forces macOS WindowServer to issue a repaint pass, fixing the blank Tkinter window bug."""
        try:
            self.update_idletasks()
            w = self.winfo_width()
            h = self.winfo_height()
            if w > 1 and h > 1:
                self.geometry(f"{w + 1}x{h + 1}")
                self.update_idletasks()
                self.geometry(f"{w}x{h}")
                self.update_idletasks()
            self.lift()
        except Exception:
            pass

    def _on_close(self) -> None:
        self.is_running = False
        if self.anim_job_id:
            try:
                self.after_cancel(self.anim_job_id)
            except Exception:
                pass
        try:
            if self.tg_client and self.tg_client.is_connected():
                self.loop.call_soon_threadsafe(self.tg_client.disconnect)
            self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass
        self.destroy()

    def _run_async_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.tg_client = TelegramClient("sessions/telegram", api_id, str(api_hash))
        self.loop.run_forever()

    async def _init_telegram(self) -> None:
        try:
            if not self.tg_client or not self.tg_client.is_connected():
                if self.tg_client:
                    await self.tg_client.connect()

            if not self.tg_client:
                return

            me = await self.tg_client.get_me()
            if isinstance(me, User):
                username = f"@{me.username}" if me.username else me.first_name
                name = me.first_name or "User"
                self.after(0, self._set_connected_status, True, f"{name} ({username})")
                self.after(0, self._log, f"Connected to Telegram as {name} ({username})", "success")
            else:
                self.after(0, self._set_connected_status, True, "Connected")
        except Exception as e:
            self.after(0, self._set_connected_status, False, f"Error: {str(e)}")
            self.after(0, self._log, f"Error connecting to Telegram: {e}", "error")

    def _set_connected_status(self, connected: bool, details: str) -> None:
        if connected:
            self.status_canvas_pill.itemconfig(self.status_circle, fill=ACCENT_GREEN)
            self.status_canvas_pill.itemconfig(self.status_text_id, text=f"Online: {details}", fill="#a7f3d0")
            self.start_btn.set_state(True)
            self.single_search_btn.set_state(True)
        else:
            self.status_canvas_pill.itemconfig(self.status_circle, fill=ACCENT_ROSE)
            self.status_canvas_pill.itemconfig(self.status_text_id, text=f"Offline: {details}", fill="#fecaca")
            self.start_btn.set_state(False)
            self.single_search_btn.set_state(False)

    def _start_ui_animation(self) -> None:
        """Periodic micro-animation for radar pulse, spinner, and glow."""
        if self.is_running and not self.is_paused:
            self.pulse_phase = (self.pulse_phase + 1) % 10
            # Radar pulse effect on live indicator
            glow_colors = [
                "#10b981", "#34d399", "#6ee7b7", "#a7f3d0",
                "#6ee7b7", "#34d399", "#10b981", "#059669",
                "#047857", "#059669"
            ]
            color = glow_colors[self.pulse_phase]
            self.live_radar.itemconfig(self.radar_dot, fill=color)

            # Spinner tick
            self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
            char = self.spinner_chars[self.spinner_idx]
            self.anim_spinner_lbl.config(text=char)
        elif self.is_paused:
            self.live_radar.itemconfig(self.radar_dot, fill=ACCENT_AMBER)
            self.anim_spinner_lbl.config(text="⏸")
        else:
            self.live_radar.itemconfig(self.radar_dot, fill="#475569")
            self.anim_spinner_lbl.config(text="●")

        self.anim_job_id = self.after(120, self._start_ui_animation)

    def _build_ui(self) -> None:
        # Top Header
        self._build_header()

        # Main Body Split (Left / Top: Controls & Metrics, Right / Bottom: Table & Logs)
        content_frame = tk.Frame(self, bg=BG_MAIN)
        content_frame.pack(fill="both", expand=True, padx=18, pady=(10, 16))

        # Row 1: Configuration & Control Card + Live Animation Meter Card
        top_row = tk.Frame(content_frame, bg=BG_MAIN)
        top_row.pack(fill="x", pady=(0, 10))

        self._build_config_card(top_row)
        self._build_live_meter_card(top_row)

        # Row 2: Metric Badges (Total, Found, Not Found, Success Rate)
        self._build_metrics_row(content_frame)

        # Row 3: Extracted Results Table
        self._build_table_section(content_frame)

        # Row 4: Activity Log Console
        self._build_log_console(content_frame)

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=BG_CARD, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo / Title
        left_box = tk.Frame(header, bg=BG_CARD)
        left_box.pack(side="left", padx=20, pady=12)

        title_lbl = tk.Label(
            left_box,
            text="⚡ Truecaller BD Extractor",
            font=("Helvetica", 17, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        title_lbl.pack(side="left")

        bot_badge = tk.Label(
            left_box,
            text=f"🤖 @{BOT_USERNAME}",
            font=("Helvetica", 10, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_INPUT,
            padx=10,
            pady=4,
        )
        bot_badge.pack(side="left", padx=16)

        # Status Pill (Right)
        self.status_canvas_pill = tk.Canvas(
            header,
            width=280,
            height=34,
            bg=BG_CARD,
            highlightthickness=0,
        )
        self.status_canvas_pill.pack(side="right", padx=20, pady=15)

        # Background rounded capsule
        self.status_canvas_pill.create_polygon(
            [
                16, 2,
                264, 2,
                278, 16,
                264, 32,
                16, 32,
                2, 16,
            ],
            fill="#1e293b",
            smooth=True,
        )
        self.status_circle = self.status_canvas_pill.create_oval(12, 11, 22, 21, fill=ACCENT_AMBER, outline="")
        self.status_text_id = self.status_canvas_pill.create_text(
            145, 16,
            text="Connecting to Telegram...",
            fill="#fde68a",
            font=("Helvetica", 10, "bold"),
        )

    def _build_config_card(self, parent: tk.Widget) -> None:
        card = tk.Frame(parent, bg=BG_CARD, padx=16, pady=14, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Title
        hdr_row = tk.Frame(card, bg=BG_CARD)
        hdr_row.pack(fill="x", pady=(0, 10))

        tk.Label(
            hdr_row,
            text="⚙️ Serial Generator & Controls",
            font=("Helvetica", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(side="left")

        # Inputs Grid
        grid_frame = tk.Frame(card, bg=BG_CARD)
        grid_frame.pack(fill="x", pady=2)

        # Start Number
        tk.Label(grid_frame, text="Start Number:", font=("Helvetica", 10, "bold"), fg=TEXT_MUTED, bg=BG_CARD).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.start_number_entry = tk.Entry(
            grid_frame,
            width=16,
            font=("Courier", 11, "bold"),
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.start_number_entry.insert(0, "+8801795664120")
        self.start_number_entry.grid(row=0, column=1, sticky="w", padx=6, pady=4)

        # Operator Preset Dropdown
        tk.Label(grid_frame, text="Preset Operator:", font=("Helvetica", 10, "bold"), fg=TEXT_MUTED, bg=BG_CARD).grid(row=0, column=2, sticky="w", padx=(12, 4), pady=4)
        self.operator_combo = ttk.Combobox(
            grid_frame,
            values=[
                "Grameenphone (017)",
                "Grameenphone (013)",
                "Robi (018)",
                "Banglalink (019)",
                "Banglalink (014)",
                "Airtel (016)",
                "Teletalk (015)",
            ],
            state="readonly",
            width=17,
        )
        self.operator_combo.set("Grameenphone (017)")
        self.operator_combo.bind("<<ComboboxSelected>>", self._on_operator_preset_changed)
        self.operator_combo.grid(row=0, column=3, sticky="w", padx=6, pady=4)

        # Quantity Count
        tk.Label(grid_frame, text="Quantity:", font=("Helvetica", 10, "bold"), fg=TEXT_MUTED, bg=BG_CARD).grid(row=0, column=4, sticky="w", padx=(12, 4), pady=4)
        self.count_entry = tk.Entry(
            grid_frame,
            width=6,
            font=("Courier", 11, "bold"),
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        self.count_entry.insert(0, "20")
        self.count_entry.grid(row=0, column=5, sticky="w", padx=6, pady=4)

        # Row 2: Delay & Single Lookup
        tk.Label(grid_frame, text="Delay (seconds):", font=("Helvetica", 10, "bold"), fg=TEXT_MUTED, bg=BG_CARD).grid(row=1, column=0, sticky="w", padx=4, pady=8)
        delay_sub = tk.Frame(grid_frame, bg=BG_CARD)
        delay_sub.grid(row=1, column=1, sticky="w", padx=6, pady=8)

        self.min_delay_entry = tk.Entry(delay_sub, width=4, font=("Courier", 11), bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.min_delay_entry.insert(0, "20")
        self.min_delay_entry.pack(side="left")

        tk.Label(delay_sub, text="to", fg=TEXT_MUTED, bg=BG_CARD, font=("Helvetica", 10)).pack(side="left", padx=4)

        self.max_delay_entry = tk.Entry(delay_sub, width=4, font=("Courier", 11), bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.max_delay_entry.insert(0, "30")
        self.max_delay_entry.pack(side="left")

        # Single Lookup
        tk.Label(grid_frame, text="Single Lookup:", font=("Helvetica", 10, "bold"), fg=TEXT_MUTED, bg=BG_CARD).grid(row=1, column=2, sticky="w", padx=(12, 4), pady=8)
        self.single_number_entry = tk.Entry(grid_frame, width=17, font=("Courier", 11), bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1, insertbackground=TEXT_PRIMARY)
        self.single_number_entry.grid(row=1, column=3, sticky="w", padx=6, pady=8)

        self.single_search_btn = ModernCanvasButton(
            grid_frame,
            text="🔍 Check",
            command=self._on_single_lookup,
            width=90,
            height=30,
            bg_color=ACCENT_INDIGO,
            hover_color="#4f46e5",
            active_color="#4338ca",
            font=("Helvetica", 9, "bold"),
        )
        self.single_search_btn.grid(row=1, column=4, columnspan=2, sticky="w", padx=(6, 0), pady=8)
        self.single_search_btn.set_state(False)

        # Action Buttons Row
        btn_row = tk.Frame(card, bg=BG_CARD)
        btn_row.pack(fill="x", pady=(10, 0))

        self.start_btn = ModernCanvasButton(
            btn_row,
            text="▶ Start Automation",
            command=self._start_automation,
            width=160,
            height=36,
            bg_color=ACCENT_GREEN,
            hover_color="#059669",
            active_color="#047857",
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        self.start_btn.set_state(False)

        self.pause_btn = ModernCanvasButton(
            btn_row,
            text="⏸ Pause",
            command=self._toggle_pause,
            width=120,
            height=36,
            bg_color=ACCENT_AMBER,
            hover_color="#d97706",
            active_color="#b45309",
        )
        self.pause_btn.pack(side="left", padx=8)
        self.pause_btn.set_state(False)

        self.stop_btn = ModernCanvasButton(
            btn_row,
            text="⏹ Stop",
            command=self._stop_automation,
            width=110,
            height=36,
            bg_color=ACCENT_ROSE,
            hover_color="#dc2626",
            active_color="#b91c1c",
        )
        self.stop_btn.pack(side="left", padx=8)
        self.stop_btn.set_state(False)

    def _build_live_meter_card(self, parent: tk.Widget) -> None:
        """The Animated Countdown & Scanning Radar Card"""
        card = tk.Frame(parent, bg=BG_CARD, width=320, padx=16, pady=14, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(side="right", fill="both", padx=(10, 0))

        # Top line with Radar Pulse indicator
        radar_header = tk.Frame(card, bg=BG_CARD)
        radar_header.pack(fill="x")

        # Radar Canvas Dot
        self.live_radar = tk.Canvas(radar_header, width=16, height=16, bg=BG_CARD, highlightthickness=0)
        self.live_radar.pack(side="left")
        self.radar_dot = self.live_radar.create_oval(2, 2, 14, 14, fill="#475569", outline="")

        self.anim_spinner_lbl = tk.Label(
            radar_header,
            text="●",
            font=("Courier", 14, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_CARD,
        )
        self.anim_spinner_lbl.pack(side="left", padx=(6, 4))

        self.live_activity_lbl = tk.Label(
            radar_header,
            text="System Idle",
            font=("Helvetica", 11, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        )
        self.live_activity_lbl.pack(side="left", padx=4)

        # Target Phone Display
        self.target_phone_display = tk.Label(
            card,
            text="Ready to extract",
            font=("Courier", 14, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_CARD,
            pady=4,
        )
        self.target_phone_display.pack(anchor="w", pady=(8, 4))

        # Animated Progress / Countdown Bar Canvas
        self.progress_canvas = tk.Canvas(card, width=280, height=12, bg=BG_INPUT, highlightthickness=0)
        self.progress_canvas.pack(fill="x", pady=6)
        self.progress_fill = self.progress_canvas.create_rectangle(0, 0, 0, 12, fill=ACCENT_GREEN, outline="")

        # Bottom Countdown Label & Status
        bot_row = tk.Frame(card, bg=BG_CARD)
        bot_row.pack(fill="x", pady=(4, 0))

        tk.Label(bot_row, text="Countdown Timer:", font=("Helvetica", 9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.countdown_digits_lbl = tk.Label(
            bot_row,
            text="--",
            font=("Helvetica", 13, "bold"),
            fg=ACCENT_AMBER,
            bg=BG_CARD,
        )
        self.countdown_digits_lbl.pack(side="right")

    def _build_metrics_row(self, parent: tk.Widget) -> None:
        metrics_bar = tk.Frame(parent, bg=BG_MAIN)
        metrics_bar.pack(fill="x", pady=(0, 10))

        self.metric_total = self._create_metric_badge(metrics_bar, "TOTAL SCANNED", "0", ACCENT_INDIGO)
        self.metric_found = self._create_metric_badge(metrics_bar, "NAMES FOUND", "0", ACCENT_GREEN)
        self.metric_not_found = self._create_metric_badge(metrics_bar, "NOT FOUND", "0", "#64748b")
        self.metric_rate = self._create_metric_badge(metrics_bar, "SUCCESS RATE", "0%", ACCENT_CYAN)

    def _create_metric_badge(self, parent: tk.Widget, label: str, val: str, color: str) -> tk.Label:
        badge = tk.Frame(parent, bg=BG_CARD, padx=16, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
        badge.pack(side="left", fill="x", expand=True, padx=4)

        # Top colored accent bar
        accent = tk.Frame(badge, bg=color, height=3)
        accent.pack(fill="x", pady=(0, 6))

        tk.Label(badge, text=label, font=("Helvetica", 8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(anchor="w")
        val_lbl = tk.Label(badge, text=val, font=("Helvetica", 18, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD)
        val_lbl.pack(anchor="w", pady=(2, 0))
        return val_lbl

    def _build_table_section(self, parent: tk.Widget) -> None:
        table_card = tk.Frame(parent, bg=BG_CARD, padx=14, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        table_card.pack(fill="both", expand=True, pady=(0, 10))

        # Action bar above table
        top_bar = tk.Frame(table_card, bg=BG_CARD)
        top_bar.pack(fill="x", pady=(0, 8))

        tk.Label(
            top_bar,
            text="📋 Extracted Contact Records",
            font=("Helvetica", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
        ).pack(side="left")

        ModernCanvasButton(
            top_bar,
            text="💾 Export CSV",
            command=self._export_csv,
            width=120,
            height=30,
            bg_color=ACCENT_CYAN,
            hover_color="#0891b2",
            active_color="#0e7490",
            font=("Helvetica", 10, "bold"),
        ).pack(side="right", padx=(8, 0))

        ModernCanvasButton(
            top_bar,
            text="🗑 Clear",
            command=self._clear_results,
            width=80,
            height=30,
            bg_color=BG_CARD_ALT,
            hover_color="#334155",
            active_color="#1e293b",
            font=("Helvetica", 10),
        ).pack(side="right")

        # Treeview with dark theme styling
        tree_container = tk.Frame(table_card, bg=BG_CARD)
        tree_container.pack(fill="both", expand=True)

        columns = ("id", "time", "phone", "name", "carrier", "country", "whatsapp", "telegram", "status")
        self.tree = ttk.Treeview(tree_container, columns=columns, show="headings", selectmode="browse")

        # Treeview dark styling
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=BG_INPUT,
            foreground=TEXT_PRIMARY,
            fieldbackground=BG_INPUT,
            rowheight=26,
            font=("Helvetica", 10),
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=BG_CARD_ALT,
            foreground=TEXT_PRIMARY,
            font=("Helvetica", 10, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", ACCENT_INDIGO)])

        # Row tag colors
        self.tree.tag_configure("found", background="#064e3b", foreground="#6ee7b7")
        self.tree.tag_configure("not_found", background=BG_INPUT, foreground=TEXT_MUTED)
        self.tree.tag_configure("rate_limit", background="#7f1d1d", foreground="#fca5a5")
        self.tree.tag_configure("incomplete", background="#78350f", foreground="#fde68a")

        self.tree.heading("id", text="#")
        self.tree.heading("time", text="Time")
        self.tree.heading("phone", text="Phone Number")
        self.tree.heading("name", text="Name")
        self.tree.heading("carrier", text="Carrier")
        self.tree.heading("country", text="Country")
        self.tree.heading("whatsapp", text="WhatsApp")
        self.tree.heading("telegram", text="Telegram")
        self.tree.heading("status", text="Status")

        self.tree.column("id", width=40, anchor="center")
        self.tree.column("time", width=80, anchor="center")
        self.tree.column("phone", width=140, anchor="w")
        self.tree.column("name", width=190, anchor="w")
        self.tree.column("carrier", width=130, anchor="w")
        self.tree.column("country", width=100, anchor="center")
        self.tree.column("whatsapp", width=80, anchor="center")
        self.tree.column("telegram", width=80, anchor="center")
        self.tree.column("status", width=110, anchor="center")

        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_log_console(self, parent: tk.Widget) -> None:
        log_card = tk.Frame(parent, bg=BG_CARD, padx=12, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
        log_card.pack(fill="x")

        hdr = tk.Frame(log_card, bg=BG_CARD)
        hdr.pack(fill="x", pady=(0, 4))
        tk.Label(hdr, text="🖥 Real-Time Activity Stream", font=("Helvetica", 9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        self.log_text = tk.Text(
            log_card,
            height=4,
            font=("Courier", 10),
            bg="#090d16",
            fg="#cbd5e1",
            relief="flat",
            highlightthickness=0,
            insertbackground="#ffffff",
        )
        self.log_text.tag_config("info", foreground="#38bdf8")
        self.log_text.tag_config("success", foreground="#34d399")
        self.log_text.tag_config("warning", foreground="#fbbf24")
        self.log_text.tag_config("error", foreground="#f87171")
        self.log_text.tag_config("timestamp", foreground="#64748b")

        log_scroll = ttk.Scrollbar(log_card, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

    def _log(self, message: str, tag: str = "info") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] ", "timestamp")
        self.log_text.insert("end", f"{message}\n", tag)
        self.log_text.see("end")

    def _on_operator_preset_changed(self, event: Optional[Any] = None) -> None:
        presets = {
            "Grameenphone (017)": "+8801700000000",
            "Grameenphone (013)": "+8801300000000",
            "Robi (018)": "+8801800000000",
            "Banglalink (019)": "+8801900000000",
            "Banglalink (014)": "+8801400000000",
            "Airtel (016)": "+8801600000000",
            "Teletalk (015)": "+8801500000000",
        }
        choice = self.operator_combo.get()
        suggested = presets.get(choice)
        if suggested:
            current = self.start_number_entry.get().strip()
            digits = re.sub(r"\D", "", current)
            if len(digits) >= 11:
                suffix = digits[3:]
                new_prefix = suggested[:6]
                self.start_number_entry.delete(0, "end")
                self.start_number_entry.insert(0, f"{new_prefix}{suffix}")
            else:
                self.start_number_entry.delete(0, "end")
                self.start_number_entry.insert(0, suggested)

    def _on_single_lookup(self) -> None:
        num = self.single_number_entry.get().strip()
        if not num:
            messagebox.showwarning("Input Required", "Please enter a phone number to check.")
            return

        is_valid, res = is_valid_phone_number(num)
        if not is_valid:
            messagebox.showerror("Invalid Number", res)
            return

        cleaned_num = res
        self.single_search_btn.set_state(False)
        self._log(f"Single lookup initiated for {cleaned_num}...", "info")
        asyncio.run_coroutine_threadsafe(self._query_single(cleaned_num), self.loop)

    async def _query_single(self, number: str) -> None:
        if not self.tg_client:
            return
        self.after(0, self._set_live_status, f"Querying {number}...", number)
        raw_text = await send_to_bot(self.tg_client, BOT_USERNAME, number, timeout=30)
        data = parse_bot_response(raw_text, number)
        self.after(0, self._add_result, data)
        self.after(0, lambda: self.single_search_btn.set_state(True))
        self.after(0, self._set_live_status, "Ready", "Single lookup done")

    def _start_automation(self) -> None:
        start_num_str = self.start_number_entry.get().strip()
        is_valid, res = is_valid_phone_number(start_num_str)
        if not is_valid:
            messagebox.showerror("Invalid Start Number", res)
            return
        start_num = res

        try:
            count = int(self.count_entry.get().strip())
            if count <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid Quantity", "Quantity must be a positive number (e.g. 20).")
            return

        try:
            min_d = float(self.min_delay_entry.get().strip())
            max_d = float(self.max_delay_entry.get().strip())
            if min_d < 5 or max_d < min_d:
                raise ValueError()
        except ValueError:
            messagebox.showerror("Invalid Delay", "Min delay must be >= 5s, and Max delay >= Min delay.")
            return

        serialized_numbers = generate_serial_numbers(start_num, count)
        if not serialized_numbers:
            messagebox.showerror("Generation Error", "No serial numbers could be generated with the given parameters.")
            return

        self.is_running = True
        self.is_paused = False

        self.start_btn.set_state(False)
        self.pause_btn.set_state(True)
        self.pause_btn.set_text("⏸ Pause")
        self.pause_btn.set_colors(ACCENT_AMBER, "#d97706", "#b45309")
        self.stop_btn.set_state(True)

        self._set_live_status("Starting automation...", f"{len(serialized_numbers)} numbers queued")
        self._log(f"Generated {len(serialized_numbers)} serialized numbers: {serialized_numbers[0]} -> {serialized_numbers[-1]}", "info")
        self._log(f"Starting automation cycle with {min_d}s - {max_d}s randomized delay...", "info")

        asyncio.run_coroutine_threadsafe(
            self._automation_worker(serialized_numbers, min_d, max_d), self.loop
        )

    def _toggle_pause(self) -> None:
        if not self.is_running:
            return

        self.is_paused = not self.is_paused
        if self.is_paused:
            self.pause_btn.set_text("▶ Resume")
            self.pause_btn.set_colors(ACCENT_GREEN, "#059669", "#047857")
            self._set_live_status("Paused", "Waiting to resume...")
            self._log("Automation paused by user.", "warning")
        else:
            self.pause_btn.set_text("⏸ Pause")
            self.pause_btn.set_colors(ACCENT_AMBER, "#d97706", "#b45309")
            self._set_live_status("Running...", "Resumed")
            self._log("Automation resumed.", "info")

    def _stop_automation(self) -> None:
        self.is_running = False
        self.is_paused = False
        self.start_btn.set_state(True)
        self.pause_btn.set_state(False)
        self.pause_btn.set_text("⏸ Pause")
        self.stop_btn.set_state(False)
        self._set_live_status("Stopped", "Automation halted")
        self.countdown_digits_lbl.config(text="--")
        self._set_progress_bar(0.0)
        self._log("Automation sequence stopped by user.", "warning")

    async def _automation_worker(
        self, numbers: List[str], min_delay: float, max_delay: float
    ) -> None:
        total = len(numbers)
        for idx, number in enumerate(numbers, 1):
            while self.is_paused and self.is_running:
                await asyncio.sleep(0.4)

            if not self.is_running:
                break

            self.after(0, self._set_live_status, f"Scanning ({idx}/{total})", number)
            self.after(0, self._set_progress_bar, float(idx - 1) / float(total))
            self.after(0, self._log, f"[{idx}/{total}] Querying {number} from @{BOT_USERNAME}...", "info")

            if not self.tg_client:
                break

            raw_text = await send_to_bot(self.tg_client, BOT_USERNAME, number, timeout=35)
            data = parse_bot_response(raw_text, number)

            self.after(0, self._add_result, data)

            if data["status"] == "Rate Limited":
                self.after(0, self._log, "⚠️ Rate limit or daily quota reached! Stopping automation.", "error")
                self.after(0, self._stop_automation)
                break

            # If more numbers remain in the sequence, start animated countdown
            if idx < total and self.is_running:
                delay = random.uniform(min_delay, max_delay)
                delay_int = int(round(delay))
                self.after(0, self._log, f"Pacing delay: waiting {delay_int}s before next query...", "info")

                start_delay_time = time.time()
                while time.time() - start_delay_time < delay:
                    if not self.is_running:
                        break
                    while self.is_paused and self.is_running:
                        await asyncio.sleep(0.4)

                    elapsed = time.time() - start_delay_time
                    remaining = max(0, int(math.ceil(delay - elapsed)))
                    fraction = min(1.0, elapsed / delay)

                    self.after(0, self.countdown_digits_lbl.config, {"text": f"{remaining}s"})
                    # Animate countdown bar filling smoothly
                    self.after(0, self._set_progress_bar, fraction)
                    await asyncio.sleep(0.2)

                self.after(0, self.countdown_digits_lbl.config, {"text": "--"})

        self.after(0, self._on_automation_finished)

    def _set_live_status(self, header_text: str, phone_text: str) -> None:
        self.live_activity_lbl.config(text=header_text)
        self.target_phone_display.config(text=phone_text)

    def _set_progress_bar(self, fraction: float) -> None:
        """Smoothly updates the canvas progress bar width."""
        w = self.progress_canvas.winfo_width() or 280
        fill_width = int(w * fraction)
        self.progress_canvas.coords(self.progress_fill, 0, 0, fill_width, 12)

    def _on_automation_finished(self) -> None:
        if self.is_running:
            self.is_running = False
            self.start_btn.set_state(True)
            self.pause_btn.set_state(False)
            self.stop_btn.set_state(False)
            self._set_live_status("Finished 🎉", "Queue completed")
            self.countdown_digits_lbl.config(text="Done")
            self._set_progress_bar(1.0)
            self._log("All serialized numbers completed successfully!", "success")
            messagebox.showinfo("Extraction Complete", "All numbers in the sequence have been processed!")

    def _add_result(self, data: Dict[str, Any]) -> None:
        self.results_data.append(data)
        item_id = len(self.results_data)
        now_time = datetime.now().strftime("%H:%M:%S")

        wa_icon = "Yes" if data.get("has_whatsapp") else "No"
        tg_icon = "Yes" if data.get("has_telegram") else "No"

        status_text = data.get("status", "Unknown")
        tag = "not_found"
        if status_text == "Found":
            tag = "found"
        elif status_text == "Rate Limited":
            tag = "rate_limit"
        elif status_text == "Search Incomplete":
            tag = "incomplete"

        self.tree.insert(
            "",
            "end",
            values=(
                item_id,
                now_time,
                data.get("phone_number", ""),
                data.get("name", ""),
                data.get("carrier", ""),
                data.get("country", ""),
                wa_icon,
                tg_icon,
                status_text,
            ),
            tags=(tag,),
        )
        self.tree.yview_moveto(1.0)

        # Update Metrics Badges
        total_count = len(self.results_data)
        found_count = sum(1 for r in self.results_data if r.get("status") == "Found")
        not_found_count = sum(1 for r in self.results_data if r.get("status") == "Not Found")
        rate = f"{(found_count / total_count * 100):.0f}%" if total_count > 0 else "0%"

        self.metric_total.config(text=str(total_count))
        self.metric_found.config(text=str(found_count))
        self.metric_not_found.config(text=str(not_found_count))
        self.metric_rate.config(text=rate)

        log_tag = "success" if status_text == "Found" else "info"
        self._log(
            f"Result for {data.get('phone_number')}: Name='{data.get('name')}', Carrier='{data.get('carrier')}', Status={status_text}",
            tag=log_tag,
        )

    def _clear_results(self) -> None:
        if self.is_running:
            messagebox.showwarning("Busy", "Cannot clear table while automation is running.")
            return

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results_data.clear()
        self.metric_total.config(text="0")
        self.metric_found.config(text="0")
        self.metric_not_found.config(text="0")
        self.metric_rate.config(text="0%")
        self._set_progress_bar(0.0)
        self._log("Extracted records cleared from view.", "info")

    def _export_csv(self) -> None:
        if not self.results_data:
            messagebox.showinfo("Export CSV", "No records to export yet.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Extracted Contacts",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"truecaller_bd_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
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
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in self.results_data:
                    writer.writerow({k: row.get(k, "") for k in fieldnames})

            self._log(f"Exported {len(self.results_data)} records to {filename}", "success")
            messagebox.showinfo("Export Successful", f"Successfully saved {len(self.results_data)} contacts to:\n{filename}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Failed to save CSV file:\n{str(e)}")


def launch_gui() -> None:
    app = TruecallerExtractorApp()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
