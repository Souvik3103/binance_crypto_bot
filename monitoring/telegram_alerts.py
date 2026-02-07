import requests
import os
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=BASE_DIR / ".env")


class TelegramAlerter:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            raise RuntimeError("Telegram credentials missing")

        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, message: str):
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
        }
        requests.post(self.base_url, json=payload, timeout=5)

    def send_alert(self, title: str, body: str):
        msg = f"<b>{title}</b>\n{body}"
        self.send(msg)