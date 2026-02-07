# Binance Futures Trading Bot (DRY-RUN → Live)

A **production-grade crypto futures trading system** built in Python, designed for
**capital preservation, robustness, and operational safety**.

This is **not** a signal script.
It is a **full trading system** with risk management, kill switches, monitoring, and
deployment hardening.

---

## ⚠️ DISCLAIMER (READ FIRST)

- This software trades **real financial instruments**
- Futures trading involves **significant risk**
- There are **no guarantees of profit**
- You are fully responsible for any capital used

**Use DRY-RUN mode first.**
Only trade real money after extended observation.

---

## 📌 What This System Does

### Strategy
- Trades **USDT-M Binance Futures**
- Supports **LONG and SHORT**
- Uses:
  - Donchian breakout (structure)
  - EMA trend filter
  - ATR volatility filter
- Low win-rate, **asymmetric risk/reward** (trend-following)

### Risk Management (Non-Negotiable)
- Max leverage: **2×**
- Fixed fractional risk per trade
- Isolated margin only
- Max concurrent positions: **3**
- Daily & weekly drawdown limits
- Liquidation-aware position sizing

### Safety & Operations
- Global kill switch
- Telegram alerts
- DRY-RUN mode (no orders sent)
- systemd deployment (auto-restart)
- Designed to run unattended on Raspberry Pi

---

## 🧱 Project Structure
```bash
crypto_bot/
  ├── backtest/
  ├── data/
  ├── execution/
  ├── monitoring/
  ├── risk/
  ├── strategy/
  ├── main.py
  ├── requirements.txt
  ├── .gitignore
  └── README.md
```
---

## 🛠️ Environment Setup (Fresh Machine)

### 1️⃣ System Requirements
- Linux (tested on Raspberry Pi OS)
- Python **3.11+**
- Internet connection
- Binance account (Futures enabled)

---

### 2️⃣ Clone the Repository
```bash
git clone https://github.com/your-username/binance_crypto_bot.git
cd binance_crypto_bot
```
---

### 3️⃣ Create Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
```
---

### 4️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```
---

## 🔐 Configuration (.env)

Create a `.env` file (**never commit this**):
```bash
BINANCE_FUTURES_KEY=your_key_here  
BINANCE_FUTURES_SECRET=your_secret_here  

TELEGRAM_BOT_TOKEN=your_bot_token  
TELEGRAM_CHAT_ID=your_chat_id  

chmod 600 .env
```
---

## ▶️ Running the Bot
```bash
source venv/bin/activate  
python main.py
```
---

## 🔄 DRY-RUN MODE
```bash
DRY_RUN = True  
```
Run for **7–14 days** before real trading.

---

## 🚨 Kill Switch

Trading halts on:
- API errors
- Equity anomalies
- Unexpected open positions
- Manual trigger

Telegram alert is sent immediately.

---

## ⚙️ systemd Deployment

The bot can be deployed as a systemd service for:
- Auto-start on boot
- Auto-restart on crash
- Persistent logs

---

## 🚀 Going Live

Only after extended DRY-RUN validation:
```bash
DRY_RUN = False  
```
Start with **₹1,000–₹2,000** only.

---

## 📈 Philosophy

This system prioritizes:
- Survival
- Discipline
- Risk asymmetry
- Operational robustness

Boring systems survive.

---

## 📜 License

Use at your own risk.
No warranty.
No liability.
