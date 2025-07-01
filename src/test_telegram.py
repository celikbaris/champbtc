# src/test_telegram.py

from notifications import send_telegram_message, TOKEN, CHAT_ID

def run_test():
    """
    Sends a single test message to Telegram to verify the configuration.
    """
    print("--- Telegram Notification Test Script ---")
    
    if not TOKEN or "YOUR_TELEGRAM_BOT_TOKEN_HERE" in TOKEN:
        print("\n❌ ERROR: Telegram TOKEN is missing or invalid in your config.ini file.")
        print("   Please get your token from BotFather and add it to the [TELEGRAM] section.")
        return
        
    if not CHAT_ID or "YOUR_TELEGRAM_CHAT_ID_HERE" in CHAT_ID:
        print("\n❌ ERROR: Telegram CHAT_ID is missing or invalid in your config.ini file.")
        print("   Please get your ID from @userinfobot and add it to the [TELEGRAM] section.")
        return
        
    print(f"\nFound Token: ...{TOKEN[-6:]}")
    print(f"Found Chat ID: {CHAT_ID}")
    
    print("\nAttempting to send test message...")
    
    test_message = (
        "✅ *Telegram Test Successful* ✅\n\n"
        "If you received this message, your Champion Trader Bot is correctly configured to send notifications."
    )
    
    send_telegram_message(test_message)
    
    print("\n--- Test Complete ---")
    print("Please check your Telegram app for the message.")

if __name__ == '__main__':
    run_test()