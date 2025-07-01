# src/dashboard.py

import streamlit as st
import pandas as pd
import json
import os
import time

# --- CONFIGURATION ---
STATE_FILE_PATH = "dashboard_state.json"
st.set_page_config(
    layout="wide",
    page_title="Champion Trader Live Dashboard",
    page_icon="🏆"
)

# --- HELPER FUNCTIONS ---
def get_pnl_color(pnl):
    if pnl > 0: return "green"
    if pnl < 0: return "red"
    return "gray"

def get_status_icon(status):
    if status == "Running": return "✅"
    if status == "Error": return "💥"
    return "…_loading"

def render_metric(label, value, help_text=""):
    st.metric(label, value, help=help_text)

# --- UI LAYOUT ---
st.title("🏆 Champion Trader Live Dashboard")
status_placeholder = st.empty()
st.markdown("---")

tab1, tab2, tab3 = st.tabs(["**Current Position**", "**Signal Analysis**", "**Bot Internals & Sizing**"])

# Create placeholders within each tab
with tab1:
    position_placeholder = st.empty()
with tab2:
    signal_placeholder = st.empty()
with tab3:
    internals_placeholder = st.empty()


# --- MAIN UI LOOP ---
while True:
    try:
        # To avoid file read errors if the bot is writing at the same time
        with open(STATE_FILE_PATH, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        with status_placeholder.container():
            st.warning("Dashboard is waiting for the bot's first data file (`dashboard_state.json`)... Make sure live_bot.py is running.", icon="⏳")
        time.sleep(5)
        continue

    # --- 1. STATUS BAR (TOP) ---
    with status_placeholder.container():
        status = data.get("bot_status", "Unknown")
        icon = get_status_icon(status)
        mode = "Paper Trading" if data.get('paper_trading', True) else "🔴 LIVE TRADING"
        
        st.header(f"{icon} Bot Status: **{status}** in **{mode}**")
        st.caption(f"Last Update: {data.get('last_update', 'N/A')}")
        
        if status == "Error":
            st.error(f"**Error Message:** {data.get('error_message', 'No details provided.')}")

    # --- 2. CURRENT POSITION TAB ---
    with position_placeholder.container():
        pos_info = data.get("position_info")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            col1.metric("Account Balance", f"${data.get('account_balance', 0):,.2f}")
        with col2:
            current_price = data.get("signal_analysis", {}).get("Latest Price", 0)
            col2.metric("Current BTC Price", f"${current_price:,.2f}")

        st.markdown("#### Position Details")
        if pos_info:
            if pos_info['type'] == 'long':
                st.success("### 🟢 ACTIVE LONG POSITION")
            else:
                st.error("### 🔴 ACTIVE SHORT POSITION")

            p1, p2, p3 = st.columns(3)
            p1.metric("Entry Price", f"${pos_info['entry_price']:,.2f}")
            p2.metric("Position Size (USD)", f"${pos_info['size_usd']:,.2f}", f"{pos_info['size_units']:.6f} BTC")
            p3.metric("Current Stop-Loss", f"${pos_info['stop_loss']:,.2f}")

            pnl_usd = pos_info.get("unrealized_pnl_usd", 0)
            pnl_pct = pos_info.get("unrealized_pnl_pct", 0)
            pnl_color = get_pnl_color(pnl_usd)
            
            st.metric("Unrealized PnL", f"${pnl_usd:,.2f}", f"{pnl_pct:.2f}%")
            st.markdown(f"<style>div[data-testid='stMetric-d{1}'] > div > div {{ color: {pnl_color}; }}</style>", unsafe_allow_html=True)
        else:
            st.info("⚖️ **No active position.** The bot is currently monitoring the market for a valid entry signal.")

    # --- 3. SIGNAL ANALYSIS TAB ---
    with signal_placeholder.container():
        analysis = data.get("signal_analysis", {})
        if not analysis:
            st.warning("No signal analysis data available yet.")
        else:
            st.subheader("Model Predictions vs. Thresholds")
            c1, c2 = st.columns(2)
            c1.metric("Long Model Prediction", f"{analysis.get('Pred Long', 0):.4f}", f"Threshold: {analysis.get('Long Threshold', 0):.4f}")
            c2.metric("Short Model Prediction", f"{analysis.get('Pred Short', 0):.4f}", f"Threshold: {analysis.get('Short Threshold', 0):.4f}")

            st.subheader("Entry Signal Checklist")
            checks = {
                "Long Signal Strong Enough?": analysis.get('Go Long Signal', False),
                "Short Signal Strong Enough?": analysis.get('Go Short Signal', False),
                "Signals Are Not Conflicting?": analysis.get('Is Clear Signal', False),
                "Market Volatility High Enough?": analysis.get('Volatility Passed', False)
            }
            
            final_decision = "AWAITING"
            if checks["Market Volatility High Enough?"]:
                if checks["Signals Are Not Conflicting?"]:
                    if checks["Long Signal Strong Enough?"]:
                        final_decision = "🟢 GO LONG"
                    elif checks["Short Signal Strong Enough?"]:
                        final_decision = "🔴 GO SHORT"
                else:
                    final_decision = "CONFLICT"
            else:
                final_decision = "TOO QUIET"

            for check, passed in checks.items():
                st.markdown(f"- {check}: {'✅' if passed else '❌'}")
            
            if final_decision == "🟢 GO LONG":
                st.success(f"**Final Decision: All checks passed. Preparing to enter a LONG position.**")
            elif final_decision == "🔴 GO SHORT":
                st.error(f"**Final Decision: All checks passed. Preparing to enter a SHORT position.**")
            elif final_decision == "CONFLICT":
                st.warning(f"**Final Decision: HOLD. Both long and short signals are active.**")
            elif final_decision == "TOO QUIET":
                st.warning(f"**Final Decision: HOLD. Market volatility is below the required filter.**")
            else:
                st.info(f"**Final Decision: HOLD. Conditions for entry are not met.**")


    # --- 4. BOT INTERNALS & SIZING TAB ---
    with internals_placeholder.container():
        st.subheader("Next Trade Sizing Logic")
        sizing = data.get("sizing_info")
        pos_info = data.get("position_info")
        
        if sizing and not pos_info:
            st.info("The following calculation will be used for the **next** trade, assuming current conditions hold.")
            sc1, sc2, sc3 = st.columns(3)
            
            balance = sizing.get('account_balance', 0)
            risk_pct = sizing.get('risk_per_trade_pct', 0)
            risk_usd = sizing.get('capital_to_risk_usd', 0)
            risk_unit = sizing.get('risk_per_unit_usd', 0)
            calc_size = sizing.get('calculated_position_size', 0)

            sc1.metric("Account Balance", f"${balance:,.2f}")
            sc2.metric("Risk per Trade", f"{risk_pct:.0%}", f"(${risk_usd:,.2f})")
            sc3.metric("Risk per Unit (Price to SL)", f"${risk_unit:,.2f}")

            st.markdown("#### Position Size Calculation")
            st.code(f"Position Size = Capital to Risk / Risk per Unit\n              = ${risk_usd:,.2f} / ${risk_unit:,.2f}\n              = {calc_size:.6f} BTC", language='bash')
            
        elif pos_info:
            st.info("Sizing information will be displayed here once the current position is closed.")
        else:
            st.warning("Sizing data not yet available.")
            
        st.subheader("Volatility Internals")
        analysis = data.get("signal_analysis", {})
        if analysis:
            vc1, vc2 = st.columns(2)
            vc1.metric("Current Volatility (10-period)", f"{analysis.get('Volatility', 0):.6f}")
            vc2.metric("Volatility Filter (50-period avg)", f"{analysis.get('Volatility Filter', 0):.6f}", "Bot only trades if Current > Filter")

    # --- REFRESH ---
    time.sleep(5)