import time
import ccxt
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

from data.candles import CandleLoader
from strategy.futures_breakdown_15m import FuturesBreakdown15m
from risk.risk_futures import FuturesRiskManager
from risk.kill_switch import KillSwitch
from execution.broker_binance_futures import BinanceFuturesBroker
from monitoring.telegram_alerts import TelegramAlerter


# ---------------- CONFIG ----------------

TIMEFRAME = "15m"
SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "BNB/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "AVAX/USDT",
    "LINK/USDT",
]

WARMUP_BARS = 300
POLL_INTERVAL_SEC = 30
DRY_RUN = True   # MUST stay True until going live
MAX_EXPECTED_POSITIONS = 3


# ---------------- UTILS ----------------

def wait_for_next_candle(timeframe_minutes: int):
    while True:
        now = datetime.now(timezone.utc)
        if now.minute % timeframe_minutes == 0 and now.second < 5:
            return
        time.sleep(1)


def emergency_close_all(broker: BinanceFuturesBroker):
    positions = broker.exchange.fetch_positions()
    for p in positions:
        if abs(p["contracts"]) > 0:
            broker.emergency_close(
                symbol=p["symbol"],
                side=p["side"],
                qty=abs(p["contracts"]),
            )


# ---------------- MAIN ----------------

def main():
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(dotenv_path=BASE_DIR / ".env")

    alerter = TelegramAlerter()
    kill_switch = KillSwitch()

    exchange = ccxt.binance({
        "enableRateLimit": True,
        "options": {"defaultType": "future"},
    })

    loader = CandleLoader(exchange, timeframe=TIMEFRAME)
    strategy = FuturesBreakdown15m()
    risk_manager = FuturesRiskManager()
    broker = BinanceFuturesBroker()

    print("=== Futures bot started ===")

    # ---- Startup alert ----
    alerter.send_alert(
        "BOT STARTED",
        f"Mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}\n"
        f"Time: {datetime.now(timezone.utc)}"
    )

    # ---- Initial equity ----
    balance = broker.exchange.fetch_balance({"type": "future"})
    equity = balance["total"].get("USDT", 0.0)
    print("FUTURES USDT BALANCE:", equity)

    risk_manager.reset_daily(equity)
    risk_manager.reset_weekly(equity)

    # ---- Preload candles ----
    for symbol in SYMBOLS:
        loader.load(symbol)

    # ---------------- LOOP ----------------
    while True:
        wait_for_next_candle(15)

        print(f"\n[{datetime.now(timezone.utc)}] New candle detected")
        print(f"[HEARTBEAT] Bot alive")

        # ---- Kill switch guard ----
        if kill_switch.is_active():
            alerter.send_alert(
                "KILL SWITCH ACTIVE",
                f"Reason: {kill_switch.reason()}\nTrading halted."
            )
            if not DRY_RUN:
                emergency_close_all(broker)
            break

        # ---- Refresh equity ----
        try:
            balance = broker.exchange.fetch_balance({"type": "future"})
            equity = balance["total"].get("USDT", 0.0)
        except Exception as e:
            kill_switch.trigger(f"Balance fetch failed: {e}")
            continue

        # ---- Drawdown guard ----
        dd_check = risk_manager.check_drawdown(equity)
        if not dd_check.approved:
            kill_switch.trigger(dd_check.reason)
            continue

        # ---- Position sanity ----
        try:
            all_positions = broker.exchange.fetch_positions()
            open_positions = [p for p in all_positions if abs(p["contracts"]) > 0]

            if len(open_positions) > MAX_EXPECTED_POSITIONS:
                kill_switch.trigger(
                    f"Unexpected open positions: {len(open_positions)}"
                )
                continue
        except Exception as e:
            kill_switch.trigger(f"Position fetch failed: {e}")
            continue

        # ---- Symbol loop ----
        for symbol in SYMBOLS:
            if kill_switch.is_active():
                break

            try:
                df = loader.load(symbol)

                if len(df) < WARMUP_BARS:
                    continue

                symbol_positions = broker.exchange.fetch_positions([symbol])
                position_open = any(abs(p["contracts"]) > 0 for p in symbol_positions)

                signal = strategy.generate_signal(
                    symbol=symbol,
                    df=df.tail(400),
                    position_open=position_open,
                    risk_manager=risk_manager,
                    equity=equity,
                    open_positions={},  # exchange is source of truth
                )

                if not signal:
                    continue

                tp_price = (
                    signal.entry_price + 2 * signal.atr
                    if signal.side == "long"
                    else signal.entry_price - 2 * signal.atr
                )

                msg = (
                    f"<b>[{'DRY-RUN' if DRY_RUN else 'LIVE'} FUTURES SIGNAL]</b>\n"
                    f"Symbol: {symbol}\n"
                    f"Side: {signal.side.upper()}\n"
                    f"Qty: {signal.qty:.4f}\n"
                    f"Entry: {signal.entry_price:.2f}\n"
                    f"Stop: {signal.stop_loss:.2f}\n"
                    f"TP: {tp_price:.2f}\n"
                    f"Liq: {signal.liquidation_price:.2f}\n"
                    f"Time: {datetime.now(timezone.utc)}"
                )

                print(msg)
                alerter.send(msg)

                if DRY_RUN:
                    continue

                # ---- LIVE EXECUTION ----
                broker.set_isolated_margin(symbol)
                broker.set_leverage(symbol, 2)

                broker.place_entry(symbol=symbol, side=signal.side, qty=signal.qty)
                broker.place_stop_loss(
                    symbol=symbol,
                    side=signal.side,
                    qty=signal.qty,
                    stop_price=signal.stop_loss,
                )
                broker.place_take_profit(
                    symbol=symbol,
                    side=signal.side,
                    qty=signal.qty,
                    take_profit=tp_price,
                )

            except Exception as e:
                kill_switch.trigger(f"Fatal error on {symbol}: {e}")
                alerter.send_alert("FATAL ERROR", f"{symbol}\n{e}")
                break

        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()