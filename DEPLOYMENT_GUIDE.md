# GCP Deployment Guide - Environment Variables

## Required Environment Variables

Set these environment variables on your GCP instance before running the bot:

| Variable Name | Description | Required | Example |
|---------------|-------------|----------|---------|
| `BINANCE_API_KEY` | Your Binance API key for trading | **YES** | `pI58h6rWsD2tBPWtstjYsaAh1uuu9ye5fO7wckRWf0aQO21op3iKRQ0RvUQDtzoi` |
| `BINANCE_API_SECRET` | Your Binance API secret for trading | **YES** | `5q6GOvgIWD9DhEIGkQOxJbZb8g4je76m83NxvCOS73M0m4CXmntIao2XUSX1uXdR` |
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token for notifications | Optional | `7315335798:AAH-IIfetB_DQ0clE0K865hIe7mzFCR3Ch4` |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID for notifications | Optional | `5827431685` |

## How to Set Environment Variables on GCP Instance

### Method 1: Set in SSH session (temporary)
```bash
export BINANCE_API_KEY="pI58h6rWsD2tBPWtstjYsaAh1uuu9ye5fO7wckRWf0aQO21op3iKRQ0RvUQDtzoi"
export BINANCE_API_SECRET="5q6GOvgIWD9DhEIGkQOxJbZb8g4je76m83NxvCOS73M0m4CXmntIao2XUSX1uXdR"
export TELEGRAM_BOT_TOKEN="7315335798:AAH-IIfetB_DQ0clE0K865hIe7mzFCR3Ch4"
export TELEGRAM_CHAT_ID="5827431685"
```

### Method 2: Add to ~/.bashrc (persistent)
```bash
echo 'export BINANCE_API_KEY="your_api_key_here"' >> ~/.bashrc
echo 'export BINANCE_API_SECRET="your_api_secret_here"' >> ~/.bashrc
echo 'export TELEGRAM_BOT_TOKEN="your_telegram_token_here"' >> ~/.bashrc
echo 'export TELEGRAM_CHAT_ID="your_chat_id_here"' >> ~/.bashrc
source ~/.bashrc
```

### Method 3: Create .env file (recommended for production)
Create a `.env` file in your project directory:
```bash
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
TELEGRAM_BOT_TOKEN=your_telegram_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Security Notes

- ✅ **Sensitive data removed** from `config.ini`
- ✅ **Bot now reads from environment variables first**
- ✅ **Fallback to config.ini for non-sensitive settings**
- ✅ **Error checking added** for missing API credentials

## Verification Commands

Check if environment variables are set correctly:
```bash
echo $BINANCE_API_KEY
echo $BINANCE_API_SECRET
echo $TELEGRAM_BOT_TOKEN
echo $TELEGRAM_CHAT_ID
```

## Production Deployment Steps

1. **Upload your bot files** to GCP instance (excluding sensitive config.ini)
2. **Set environment variables** using one of the methods above
3. **Install Python dependencies**: `pip install -r requirements.txt`
4. **Test the bot**: `python src/live_bot.py`
5. **Set up process management** (screen/tmux/systemd)
6. **Monitor logs** for any issues

## Dashboard Access (Optional)

To access the Streamlit dashboard:
```bash
# Run dashboard on port 8501
streamlit run src/dashboard.py --server.port 8501 --server.address 0.0.0.0
```

Then access via: `http://YOUR_GCP_INSTANCE_IP:8501`

**Note**: Make sure to configure firewall rules for port 8501 in GCP Console. 