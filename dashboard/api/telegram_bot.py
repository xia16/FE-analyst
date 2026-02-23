"""
Telegram Bot — Trade SMS Parser & Portfolio Tracker

Listens for forwarded trade SMS messages from the Telegram bot,
parses buy/sell orders, and updates a SQLite portfolio database.

Message format (Standard Chartered):
  【STANCHART】SCB: Order filled: Buy 100 shares of MU MICRON TECHNOLOGY ORD on NMS at USD415.35. Ref. OAPOF2K88867890
  【STANCHART】SCB: Order Partially filled: Sell 508 shares of KLAR KLARNA GROUP ORD on NYS at USD13.91. Ref. OAPOF2K88803120
"""

import re
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent / "portfolio.db"

# ---------------------------------------------------------------------------
# Trade message parser
# ---------------------------------------------------------------------------

TRADE_RE = re.compile(
    r"(?:Order\s+(?:Partially\s+)?filled):\s*"
    r"(Buy|Sell)\s+"
    r"(\d+)\s+shares?\s+of\s+"
    r"(\w+)\s+"           # ticker (first word after "of")
    r"(.+?)\s+ORD\s+"     # company name (everything up to ORD)
    r"on\s+(\w+)\s+"      # exchange
    r"at\s+USD(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def parse_trade_message(text: str) -> dict | None:
    """Parse a Standard Chartered trade SMS into structured data."""
    m = TRADE_RE.search(text)
    if not m:
        return None
    action, qty, ticker, name, exchange, price = m.groups()
    return {
        "action": action.upper(),
        "ticker": ticker.upper(),
        "name": name.strip(),
        "exchange": exchange.upper(),
        "quantity": int(qty),
        "price": float(price),
        "raw_message": text,
    }


# ---------------------------------------------------------------------------
# SQLite database
# ---------------------------------------------------------------------------

def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            exchange TEXT,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            total_value REAL NOT NULL,
            ref_id TEXT,
            raw_message TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS holdings (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            exchange TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            avg_cost REAL NOT NULL DEFAULT 0,
            total_invested REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS realized_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            name TEXT,
            quantity INTEGER NOT NULL,
            buy_avg_cost REAL NOT NULL,
            sell_price REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            realized_pct REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def record_trade(trade: dict) -> dict:
    """Record a trade and update holdings. Returns the updated holding."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.utcnow().isoformat()
    total_value = trade["quantity"] * trade["price"]

    # Extract ref ID from raw message
    ref_match = re.search(r"Ref\.\s*(\S+)", trade.get("raw_message", ""))
    ref_id = ref_match.group(1) if ref_match else None

    # Check for duplicate ref_id
    if ref_id:
        existing = conn.execute("SELECT id FROM trades WHERE ref_id = ?", (ref_id,)).fetchone()
        if existing:
            conn.close()
            return {"status": "duplicate", "ref_id": ref_id}

    # Insert trade
    conn.execute(
        "INSERT INTO trades (timestamp, action, ticker, name, exchange, quantity, price, total_value, ref_id, raw_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (now, trade["action"], trade["ticker"], trade["name"], trade["exchange"],
         trade["quantity"], trade["price"], total_value, ref_id, trade.get("raw_message", "")),
    )

    # Update holdings
    row = conn.execute("SELECT * FROM holdings WHERE ticker = ?", (trade["ticker"],)).fetchone()

    if trade["action"] == "BUY":
        if row:
            new_qty = row["quantity"] + trade["quantity"]
            new_invested = row["total_invested"] + total_value
            new_avg = new_invested / new_qty if new_qty > 0 else 0
            conn.execute(
                "UPDATE holdings SET quantity = ?, avg_cost = ?, total_invested = ?, name = ?, exchange = ? WHERE ticker = ?",
                (new_qty, new_avg, new_invested, trade["name"], trade["exchange"], trade["ticker"]),
            )
        else:
            conn.execute(
                "INSERT INTO holdings (ticker, name, exchange, quantity, avg_cost, total_invested) VALUES (?, ?, ?, ?, ?, ?)",
                (trade["ticker"], trade["name"], trade["exchange"], trade["quantity"], trade["price"], total_value),
            )
    elif trade["action"] == "SELL":
        if row:
            sell_qty = min(trade["quantity"], row["quantity"])
            avg_cost = row["avg_cost"]
            # Record realized P&L
            if sell_qty > 0 and avg_cost > 0:
                pnl = (trade["price"] - avg_cost) * sell_qty
                pnl_pct = ((trade["price"] - avg_cost) / avg_cost) * 100
                conn.execute(
                    "INSERT INTO realized_pnl (timestamp, ticker, name, quantity, buy_avg_cost, sell_price, realized_pnl, realized_pct) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (now, trade["ticker"], trade.get("name", row["name"]), sell_qty, avg_cost, trade["price"], round(pnl, 2), round(pnl_pct, 2)),
                )
            new_qty = max(0, row["quantity"] - trade["quantity"])
            new_invested = avg_cost * new_qty if new_qty > 0 else 0
            if new_qty == 0:
                conn.execute("DELETE FROM holdings WHERE ticker = ?", (trade["ticker"],))
            else:
                conn.execute(
                    "UPDATE holdings SET quantity = ?, total_invested = ? WHERE ticker = ?",
                    (new_qty, new_invested, trade["ticker"]),
                )

    conn.commit()

    # Return updated holding
    holding = conn.execute("SELECT * FROM holdings WHERE ticker = ?", (trade["ticker"],)).fetchone()
    conn.close()

    result = {
        "status": "recorded",
        "trade": {
            "action": trade["action"],
            "ticker": trade["ticker"],
            "name": trade["name"],
            "quantity": trade["quantity"],
            "price": trade["price"],
            "total_value": total_value,
            "ref_id": ref_id,
            "timestamp": now,
        },
    }
    if holding:
        result["holding"] = dict(holding)
    else:
        result["holding"] = {"ticker": trade["ticker"], "quantity": 0, "note": "Position closed"}

    return result


def get_holdings() -> list[dict]:
    """Get all current holdings."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM holdings WHERE quantity > 0 ORDER BY ticker").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_trades(limit: int = 50) -> list[dict]:
    """Get recent trade history."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_realized_pnl(limit: int = 100) -> list[dict]:
    """Get realized P&L records."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM realized_pnl ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_realized_summary() -> dict:
    """Get total realized P&L summary."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT COALESCE(SUM(realized_pnl), 0) as total_pnl, COUNT(*) as trade_count, "
        "COALESCE(SUM(CASE WHEN realized_pnl > 0 THEN 1 ELSE 0 END), 0) as winners, "
        "COALESCE(SUM(CASE WHEN realized_pnl < 0 THEN 1 ELSE 0 END), 0) as losers "
        "FROM realized_pnl"
    ).fetchone()
    conn.close()
    return dict(row) if row else {"total_pnl": 0, "trade_count": 0, "winners": 0, "losers": 0}


def get_portfolio_summary() -> dict:
    """Get portfolio summary with total invested."""
    holdings = get_holdings()
    total_invested = sum(h["total_invested"] for h in holdings)
    return {
        "holdings_count": len(holdings),
        "total_invested": round(total_invested, 2),
        "holdings": holdings,
    }


# Initialize DB on import
init_db()
