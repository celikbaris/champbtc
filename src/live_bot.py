# src/live_bot.py

import ccxt
import pandas as pd
import numpy as np
import xgboost as xgb
from ta.volatility import AverageTrueRange
from sklearn.preprocessing import MinMaxScaler
import time, json, os, traceback, configparser
from notifications import send_telegram_message, format_entry_message, format_exit_message

def load_config():
    """Loads settings from the config.ini file."""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.ini')
    if not os.path.exists(config_path): raise FileNotFoundError("config.ini not found!")
    config.read(config_path)
    return config

# --- SETUP FROM CONFIG ---
config = load_config()
# Use environment variables first, fallback to config
API_KEY = os.getenv('BINANCE_API_KEY') or config['API']['KEY']
API_SECRET = os.getenv('BINANCE_API_SECRET') or config['API']['SECRET']

# Validate that API credentials are provided
if not API_KEY or not API_SECRET:
    raise ValueError("❌ CRITICAL: Binance API credentials not found! Set BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
SYMBOL = config['TRADING']['SYMBOL']
BASE_TIMEFRAME, STRATEGY_TIMEFRAME = config['TRADING']['BASE_TIMEFRAME'], config['TRADING']['STRATEGY_TIMEFRAME']
LONG_PRED_THRESHOLD, SHORT_PRED_THRESHOLD = config.getfloat('TRADING', 'LONG_THRESHOLD'), config.getfloat('TRADING', 'SHORT_THRESHOLD')
VOLATILITY_FILTER = config.getfloat('TRADING', 'VOLATILITY_FILTER')
RISK_PER_TRADE_PCT, MAX_ALLOCATION_PCT, ATR_MULTIPLIER_SL = config.getfloat('TRADING', 'RISK_PER_TRADE_PCT'), config.getfloat('TRADING', 'MAX_ALLOCATION_PCT'), config.getfloat('TRADING', 'ATR_MULTIPLIER_SL')
MODEL_DIR, LONG_MODEL_NAME, SHORT_MODEL_NAME, STATE_FILE = config['PATHS']['MODEL_DIR'], config['MODELS']['LONG_MODEL_NAME'], config['MODELS']['SHORT_MODEL_NAME'], config['PATHS']['STATE_FILE']
PAPER_ACCOUNT_STATE, TRADE_LOG = config['PATHS']['PAPER_ACCOUNT_STATE'], config['PATHS']['TRADE_LOG']

PAPER_TRADING = True
PAPER_TRADE_INITIAL_BALANCE = 100.0

# --- Exchange and Model Setup ---
exchange = ccxt.binance({'apiKey': API_KEY, 'secret': API_SECRET, 'enableRateLimit': True})
exchange.session.trust_env = True

def load_models():
    long_model_path, short_model_path = os.path.join(MODEL_DIR, LONG_MODEL_NAME), os.path.join(MODEL_DIR, SHORT_MODEL_NAME)
    if not os.path.exists(long_model_path) or not os.path.exists(short_model_path): raise FileNotFoundError(f"Model files not found in '{MODEL_DIR}'.")
    long_model, short_model = xgb.XGBRegressor(), xgb.XGBRegressor(); long_model.load_model(long_model_path); short_model.load_model(short_model_path)
    print("✅ Champion models loaded successfully."); return long_model, short_model

def save_state(state, file_path):
    with open(file_path, 'w') as f: json.dump(state, f, indent=4)

def load_state(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {}
    return {}

def execute_trade(trade_type, amount, price):
    if PAPER_TRADING: return True
    try:
        print(f"\n🚨 [REAL TRADE] Attempting {trade_type.upper()} order for {amount}...\n"); order = exchange.create_market_order(SYMBOL, trade_type, amount)
        print(f"✅ REAL TRADE EXECUTED: {order}"); return True
    except Exception as e:
        print(f"❌ TRADE FAILED: {e}"); return False

def prepare_live_data(df_3m):
    print("   Engineering features on resampled 3m data...")
    df_3m['returns'] = np.log(df_3m['close'] / df_3m['close'].shift(1))
    for lag in [1, 2, 3, 5, 10]: df_3m[f'returns_lag_{lag}'] = df_3m['returns'].shift(lag)
    df_3m['momentum_5'] = df_3m['returns'].rolling(window=5).mean(); df_3m['momentum_10'] = df_3m['returns'].rolling(window=10).mean()
    df_3m['volatility_10'] = df_3m['returns'].rolling(window=10).std(); df_3m['volatility_filter'] = df_3m['volatility_10'].rolling(50).mean()
    candle_range = (df_3m['high'] - df_3m['low']).replace(0, 0.00001); df_3m['body_pct'] = (abs(df_3m['close'] - df_3m['open']) / candle_range).fillna(0)
    df_3m['upper_wick_pct'] = ((df_3m['high'] - np.maximum(df_3m['open'], df_3m['close'])) / candle_range).fillna(0)
    df_3m['lower_wick_pct'] = ((np.minimum(df_3m['open'], df_3m['close']) - df_3m['low']) / candle_range).fillna(0)
    df_3m['taker_buy_ratio'] = (df_3m['taker_buy_base_asset_volume'] / df_3m['volume']).fillna(0.5)
    df_3m.replace([np.inf, -np.inf], np.nan, inplace=True); df_3m.dropna(inplace=True)
    features = [c for c in df_3m.columns if c.startswith(('returns', 'momentum', 'volatility', 'body', 'upper', 'lower', 'taker'))]
    scaler = MinMaxScaler(); df_3m[features] = scaler.fit_transform(df_3m[features])
    df_3m['atr'] = AverageTrueRange(df_3m['high'], df_3m['low'], df_3m['close'], 14).average_true_range()
    df_3m.dropna(inplace=True); return df_3m, features

def log_trade_to_csv(trade_details):
    log_file = TRADE_LOG
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    df = pd.DataFrame([trade_details])
    if not os.path.isfile(log_file):
        df.to_csv(log_file, index=False)
    else:
        df.to_csv(log_file, mode='a', header=False, index=False)
    print(f"✅ Trade logged to {log_file}")

# --- MAIN LOOP ---
def run_bot():
    print("🚀 Starting Champion Live Bot (v4.1 - Telegram Integrated)...")
    long_model, short_model = load_models()
    current_position = load_state(STATE_FILE).get('current_position')
    paper_account = load_state(PAPER_ACCOUNT_STATE)
    if 'balance' not in paper_account: paper_account['balance'] = PAPER_TRADE_INITIAL_BALANCE
    last_processed_timestamp = None
    dashboard_data = load_state("dashboard_state.json")

    while True:
        try:
            print(f"\n🕒 [{pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M:%S UTC')}] Main loop initiated.")
            usdt_balance = paper_account['balance'] if PAPER_TRADING else exchange.fetch_free_balance().get('USDT', 0)
            if PAPER_TRADING: print(f"   -- Paper Trading Mode -- Simulated Balance: ${usdt_balance:,.2f}")
            else: print(f"   -- Live Trading Mode -- Real Balance: ${usdt_balance:,.2f}")
            print(f"   Fetching latest 500 candles of {BASE_TIMEFRAME} data...")
            ohlcv_1m = exchange.fetch_ohlcv(SYMBOL, timeframe=BASE_TIMEFRAME, limit=500)
            df_1m = pd.DataFrame(ohlcv_1m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']); df_1m['timestamp'] = pd.to_datetime(df_1m['timestamp'], unit='ms'); df_1m.set_index('timestamp', inplace=True)
            df_1m['number_of_trades'], df_1m['taker_buy_base_asset_volume'] = 0, 0
            print(f"   Resampling {BASE_TIMEFRAME} data to {STRATEGY_TIMEFRAME}...")
            agg_dict = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum', 'number_of_trades': 'sum', 'taker_buy_base_asset_volume': 'sum'}
            df_3m = df_1m.resample(STRATEGY_TIMEFRAME).agg(agg_dict).dropna()
            latest_candle_timestamp = df_3m.index[-1]
            bot_status, signal_analysis, position_info, sizing_info = "Waiting", dashboard_data.get('signal_analysis'), dashboard_data.get('position_info'), dashboard_data.get('sizing_info')

            if latest_candle_timestamp != last_processed_timestamp:
                bot_status = "Analyzing"
                print(f"   New candle to process: {latest_candle_timestamp}")
                processed_df, features = prepare_live_data(df_3m.copy())
                if not processed_df.empty:
                    latest_candle = processed_df.iloc[-1]; last_processed_timestamp = latest_candle.name
                    feature_values = latest_candle[features].values.reshape(1, -1)
                    predicted_long, predicted_short = long_model.predict(feature_values)[0], short_model.predict(feature_values)[0]
                    print(f"📈 Analysis: Close=${latest_candle['close']:.2f} | Pred_Long: {predicted_long:.4f} | Pred_Short: {predicted_short:.4f}")
                    signal_analysis = {"Latest Price": float(latest_candle['close']), "Pred Long": float(predicted_long), "Pred Short": float(predicted_short), "Long Threshold": LONG_PRED_THRESHOLD, "Short Threshold": SHORT_PRED_THRESHOLD, "Go Long Signal": bool(predicted_long > LONG_PRED_THRESHOLD), "Go Short Signal": bool(predicted_short > SHORT_PRED_THRESHOLD), "Is Clear Signal": bool((predicted_long > LONG_PRED_THRESHOLD) != (predicted_short > SHORT_PRED_THRESHOLD)), "Volatility": float(latest_candle['volatility_10']), "Volatility Filter": float(latest_candle['volatility_filter']), "Volatility Passed": bool(latest_candle['volatility_10'] >= latest_candle['volatility_filter'])}
                    if current_position:
                        pnl = (latest_candle['close'] - current_position['entry_price']) * current_position['position_size_units'] if current_position['type'] == 'long' else (current_position['entry_price'] - latest_candle['close']) * current_position['position_size_units']
                        position_info = {"type": current_position['type'], "entry_price": current_position['entry_price'], "size_units": current_position['position_size_units'], "size_usd": current_position['position_size_units'] * current_position['entry_price'], "stop_loss": current_position['stop_loss'], "unrealized_pnl_usd": pnl, "unrealized_pnl_pct": (pnl / (current_position['entry_price'] * current_position['position_size_units'])) * 100}
                        if current_position['type'] == 'long':
                            new_sl = latest_candle['close'] - (latest_candle['atr'] * ATR_MULTIPLIER_SL); current_position['stop_loss'] = max(current_position['stop_loss'], new_sl)
                            if latest_candle['close'] <= current_position['stop_loss']:
                                print(f"❗️ STOP-LOSS HIT (LONG). Exiting @ ${latest_candle['close']:.2f}")
                                exit_price = current_position['stop_loss']
                                if execute_trade('sell', current_position['position_size_units'], exit_price):
                                    pnl = (exit_price - current_position['entry_price']) * current_position['position_size_units']
                                    log_trade_to_csv({'timestamp': datetime.now(timezone.utc), 'type': 'long', 'entry_price': current_position['entry_price'], 'exit_price': exit_price, 'size_usd': position_info['size_usd'], 'pnl_usd': pnl, 'exit_reason': 'stop_loss'})
                                    msg = format_exit_message('long', current_position['entry_price'], exit_price, pnl, 'stop_loss')
                                    send_telegram_message(msg)
                                    if PAPER_TRADING: paper_account['balance'] += pnl
                                    current_position, position_info = None, None
                        elif current_position['type'] == 'short':
                            new_sl = latest_candle['close'] + (latest_candle['atr'] * ATR_MULTIPLIER_SL); current_position['stop_loss'] = min(current_position['stop_loss'], new_sl)
                            if latest_candle['close'] >= current_position['stop_loss']:
                                print(f"❗️ STOP-LOSS HIT (SHORT). Exiting @ ${latest_candle['close']:.2f}")
                                exit_price = current_position['stop_loss']
                                if execute_trade('buy', current_position['position_size_units'], exit_price):
                                    pnl = (current_position['entry_price'] - exit_price) * current_position['position_size_units']
                                    log_trade_to_csv({'timestamp': datetime.now(timezone.utc), 'type': 'short', 'entry_price': current_position['entry_price'], 'exit_price': exit_price, 'size_usd': position_info['size_usd'], 'pnl_usd': pnl, 'exit_reason': 'stop_loss'})
                                    msg = format_exit_message('short', current_position['entry_price'], exit_price, pnl, 'stop_loss')
                                    send_telegram_message(msg)
                                    if PAPER_TRADING: paper_account['balance'] += pnl
                                    current_position, position_info = None, None
                    if not current_position:
                        position_info = None
                        if signal_analysis['Volatility Passed']:
                            go_long, go_short = signal_analysis['Go Long Signal'], signal_analysis['Go Short Signal']
                            if go_long and not go_short:
                                entry_price = latest_candle['close']; sl_price = entry_price - (latest_candle['atr'] * ATR_MULTIPLIER_SL); risk_per_unit = entry_price - sl_price
                                sizing_info = {"account_balance": usdt_balance, "risk_per_trade_pct": RISK_PER_TRADE_PCT, "capital_to_risk_usd": usdt_balance * RISK_PER_TRADE_PCT, "entry_price": entry_price, "stop_loss_price": sl_price, "risk_per_unit_usd": risk_per_unit, "calculated_position_size": (usdt_balance * RISK_PER_TRADE_PCT) / risk_per_unit if risk_per_unit > 0 else 0}
                                if risk_per_unit > 0:
                                    print(f"💡 Entry Signal: LONG"); pos_size = sizing_info['calculated_position_size']; max_pos_value = usdt_balance * MAX_ALLOCATION_PCT
                                    if (pos_size * entry_price) > max_pos_value: pos_size = max_pos_value / entry_price
                                    if execute_trade('buy', pos_size, entry_price):
                                        msg = format_entry_message('long', entry_price, sl_price, (pos_size * entry_price), pos_size)
                                        send_telegram_message(msg)
                                        current_position = {'type': 'long', 'entry_price': entry_price, 'stop_loss': sl_price, 'position_size_units': pos_size}
                            elif go_short and not go_long:
                                entry_price = latest_candle['close']; sl_price = entry_price + (latest_candle['atr'] * ATR_MULTIPLIER_SL); risk_per_unit = sl_price - entry_price
                                sizing_info = {"account_balance": usdt_balance, "risk_per_trade_pct": RISK_PER_TRADE_PCT, "capital_to_risk_usd": usdt_balance * RISK_PER_TRADE_PCT, "entry_price": entry_price, "stop_loss_price": sl_price, "risk_per_unit_usd": risk_per_unit, "calculated_position_size": (usdt_balance * RISK_PER_TRADE_PCT) / risk_per_unit if risk_per_unit > 0 else 0}
                                if risk_per_unit > 0:
                                    print(f"💡 Entry Signal: SHORT"); pos_size = sizing_info['calculated_position_size']; max_pos_value = usdt_balance * MAX_ALLOCATION_PCT
                                    if (pos_size * entry_price) > max_pos_value: pos_size = max_pos_value / entry_price
                                    if execute_trade('sell', pos_size, entry_price):
                                        msg = format_entry_message('short', entry_price, sl_price, (pos_size * entry_price), pos_size)
                                        send_telegram_message(msg)
                                        current_position = {'type': 'short', 'entry_price': entry_price, 'stop_loss': sl_price, 'position_size_units': pos_size}
                        else: print("   Filter: Market too quiet. No new entries."); sizing_info = None
            else:
                print("   No new 3m candle has formed yet. Waiting..."); sizing_info = None

            dashboard_data = {"bot_status": bot_status, "last_update": pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M:%S UTC'), "paper_trading": PAPER_TRADING, "account_balance": usdt_balance, "signal_analysis": signal_analysis, "position_info": position_info, "sizing_info": sizing_info}
            save_state(dashboard_data, "dashboard_state.json")
            save_state({'current_position': current_position}, STATE_FILE)
            if PAPER_TRADING: save_state(paper_account, PAPER_ACCOUNT_STATE)
            
            print("✅ Cycle complete. Sleeping for 60 seconds...")
            time.sleep(60)

        except Exception as e:
            print(f"💥 UNEXPECTED ERROR: {e}"); traceback.print_exc()
            error_data = {"bot_status": "Error", "last_update": pd.Timestamp.now('UTC').strftime('%Y-%m-%d %H:%M:%S UTC'), "error_message": str(e)}
            save_state(error_data, "dashboard_state.json")
            time.sleep(60)

if __name__ == '__main__':
    run_bot()