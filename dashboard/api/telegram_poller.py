"""
Telegram Bot Poller — Polls for new messages and processes trades.

Run alongside the FastAPI server to pick up trade messages
forwarded from SMS via MacroDroid → Telegram.

Usage:
    python telegram_poller.py
"""

import os
import time
import json
import logging
import urllib.request
import urllib.parse

from telegram_bot import parse_trade_message, record_trade, get_holdings, get_trades

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8461444330:AAHmtc2ZehwiCFtBe8t-cx4W2XM34ntSK5M")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8387613359")
POLL_INTERVAL = 2  # seconds


def send_message(text: str):
    """Send a message to the Telegram chat."""
    try:
        params = urllib.parse.urlencode({
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        })
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "FE-Analyst/1.0"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.warning(f"Failed to send message: {e}")


def get_updates(offset: int = 0) -> list:
    """Get new messages from Telegram."""
    try:
        params = urllib.parse.urlencode({
            "offset": offset,
            "timeout": 30,
            "allowed_updates": json.dumps(["message"]),
        })
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "FE-Analyst/1.0"})
        with urllib.request.urlopen(req, timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("ok"):
            return data.get("result", [])
    except Exception as e:
        logger.error(f"Failed to get updates: {e}")
    return []


def handle_message(text: str):
    """Process an incoming message."""
    # Try to parse as trade
    trade = parse_trade_message(text)
    if trade:
        result = record_trade(trade)
        if result["status"] == "duplicate":
            logger.info(f"Duplicate trade: {result['ref_id']}")
            return

        t = result["trade"]
        h = result["holding"]
        logger.info(f"Trade recorded: {t['action']} {t['quantity']}x {t['ticker']} @ ${t['price']}")

        emoji = "\U0001f7e2" if t["action"] == "BUY" else "\U0001f534"
        msg = (
            f"{emoji} *{t['action']}* {t['quantity']} x {t['ticker']}\n"
            f"Price: ${t['price']:.2f} | Total: ${t['total_value']:.2f}\n"
        )
        if h.get("quantity", 0) > 0:
            msg += f"Holdings: {h['quantity']} shares @ ${h.get('avg_cost', 0):.2f} avg"
        else:
            msg += "Position closed"
        send_message(msg)
        return

    # Handle commands
    text_lower = text.strip().lower()
    if text_lower in ("/holdings", "/portfolio", "holdings", "portfolio"):
        holdings = get_holdings()
        if not holdings:
            send_message("\U0001f4ca No holdings currently.")
        else:
            lines = ["\U0001f4ca *Current Holdings*\n"]
            total = 0
            for h in holdings:
                val = h["quantity"] * h["avg_cost"]
                total += val
                lines.append(f"`{h['ticker']:6s}` {h['quantity']:>6d} @ ${h['avg_cost']:.2f} = ${val:,.0f}")
            lines.append(f"\n*Total Invested:* ${total:,.0f}")
            send_message("\n".join(lines))
        return

    if text_lower in ("/trades", "trades"):
        trade_list = get_trades(10)
        if not trade_list:
            send_message("\U0001f4cb No trades recorded yet.")
        else:
            lines = ["\U0001f4cb *Recent Trades*\n"]
            for t in trade_list:
                emoji = "\U0001f7e2" if t["action"] == "BUY" else "\U0001f534"
                lines.append(f"{emoji} {t['action']} {t['quantity']}x {t['ticker']} @ ${t['price']:.2f} \u2014 {t['timestamp'][:10]}")
            send_message("\n".join(lines))
        return

    if text_lower in ("/help", "help"):
        send_message(
            "*FE-Analyst Trade Bot*\n\n"
            "I automatically track your trades from SMS notifications.\n\n"
            "*Commands:*\n"
            "/holdings \u2014 View current positions\n"
            "/trades \u2014 Recent trade history\n"
            "/help \u2014 Show this message"
        )
        return


def main():
    logger.info("Starting Telegram trade bot poller...")
    logger.info(f"Bot token: ...{BOT_TOKEN[-8:]}")
    logger.info(f"Chat ID: {CHAT_ID}")

    offset = 0

    # Skip existing messages on startup
    updates = get_updates(offset)
    if updates:
        offset = updates[-1]["update_id"] + 1
        logger.info(f"Skipped {len(updates)} existing messages, starting from offset {offset}")

    logger.info("Listening for new messages...")

    while True:
        try:
            updates = get_updates(offset)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                text = message.get("text", "")
                chat_id = str(message.get("chat", {}).get("id", ""))

                if not text:
                    continue

                # Only process messages from our chat
                if chat_id != CHAT_ID:
                    logger.info(f"Ignoring message from chat {chat_id}")
                    continue

                logger.info(f"Received: {text[:80]}...")
                handle_message(text)

        except KeyboardInterrupt:
            logger.info("Shutting down...")
            break
        except Exception as e:
            logger.error(f"Error in poll loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
