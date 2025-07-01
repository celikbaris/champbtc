# src/notifications.py

import requests
import os
from config import config # Import the central config object

# --- LOAD SETTINGS FROM THE CENTRAL CONFIG ---
# Use environment variables first, fallback to config
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or config.get('TELEGRAM', 'TOKEN', fallback=None)
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID') or config.get('TELEGRAM', 'CHAT_ID', fallback=None)

def send_telegram_message(message):
    """Sends a message to the configured Telegram chat with proper escaping."""
    if not TOKEN or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in TOKEN:
        print("Telegram TOKEN is not configured. Skipping notification.")
        return
    if not CHAT_ID or "YOUR_TELEGRAM_CHAT_ID_HERE" in CHAT_ID:
        print("Telegram CHAT_ID is not configured. Skipping notification.")
        return

    reserved_chars = r'_*[]()~`>#+-=|{}.!'
    escaped_message = "".join(['\\' + char if char in reserved_chars else char for char in message])

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {'chat_id': CHAT_ID, 'text': escaped_message, 'parse_mode': 'MarkdownV2'}
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Telegram notification sent successfully.")
        else:
            print(f"❌ Failed to send Telegram notification. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"❌ An exception occurred while sending Telegram notification: {e}")

def format_entry_message(position_type, entry_price, stop_loss, size_usd, size_units):
    """Formats a message for a new trade entry."""
    icon = "🟢" if position_type.upper() == "LONG" else "🔴"
    message = (
        f"{icon} *NEW TRADE ENTRY* {icon}\n\n"
        f"*Type:* `{position_type.upper()}`\n"
        f"*Entry Price:* `${entry_price:,.2f}`\n"
        f"*Initial Stop-Loss:* `${stop_loss:,.2f}`\n"
        f"*Position Size:* `${size_usd:,.2f}`\n"
        f"*Amount:* `{size_units:.6f} BTC`"
    )
    return message

def format_exit_message(position_type, entry_price, exit_price, pnl, exit_reason):
    """Formats a message for a trade exit."""
    icon = "✅" if pnl >= 0 else "❌"
    message = (
        f"{icon} *TRADE CLOSED* {icon}\n\n"
        f"*Type:* `{position_type.upper()}`\n"
        f"*Entry Price:* `${entry_price:,.2f}`\n"
        f"*Exit Price:* `${exit_price:,.2f}`\n"
        f"*PnL:* `${pnl:,.2f}`\n"
        f"*Reason:* `{exit_reason}`"
    )
    return message