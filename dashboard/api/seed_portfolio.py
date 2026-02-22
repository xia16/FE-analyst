"""
Seed the portfolio database with Singapore brokerage holdings.

Parses holdings data with avg cost basis and current gain/loss %,
then inserts directly into the holdings table.

Usage:
    python seed_portfolio.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "portfolio.db"

# Portfolio name for this set of holdings
PORTFOLIO_NAME = "SG Brokerage"

# Holdings data: (ticker, name, shares, avg_cost, sector, country)
# avg_cost derived from current price / (1 + gain%)
HOLDINGS = [
    # Ticker, Name, Shares, Avg Cost (USD), Sector, Country
    ("GLD", "SPDR Gold Shares", 500, 365.85, "Commodities", "US"),
    ("VOO", "Vanguard S&P 500 ETF", 15, 284.50, "ETF - Index", "US"),
    ("AFRM", "Affirm Holdings", 450, 90.00, "Fintech", "US"),
    ("ALAB", "Astera Labs", 250, 95.00, "Semiconductors", "US"),
    ("AMD", "Advanced Micro Devices", 283, 57.50, "Semiconductors", "US"),
    ("AMZN", "Amazon.com", 200, 195.00, "Tech - Cloud", "US"),
    ("ASML", "ASML Holding", 30, 322.50, "Semiconductors", "Netherlands"),
    ("CRDO", "Credo Technology", 15, 42.00, "Semiconductors", "US"),
    ("CRWV", "CrowdStrike Holdings", 350, 88.00, "Cybersecurity", "US"),
    ("DUOL", "Duolingo", 290, 330.00, "EdTech", "US"),
    ("HOOD", "Robinhood Markets", 150, 56.00, "Fintech", "US"),
    ("IBIT", "iShares Bitcoin Trust", 238, 67.00, "Crypto ETF", "US"),
    ("META", "Meta Platforms", 100, 590.00, "Tech - Social", "US"),
    ("MU", "Micron Technology", 100, 97.00, "Semiconductors", "US"),
    ("NUTX", "Nutex Health", 250, 78.00, "Healthcare", "US"),
    ("NVDA", "NVIDIA Corporation", 200, 82.50, "Semiconductors", "US"),
    ("QQQ", "Invesco QQQ Trust", 120, 498.50, "ETF - Nasdaq", "US"),
    ("TMDX", "TransMedics Group", 150, 74.50, "Healthcare", "US"),
    ("BABA", "Alibaba Group", 150, 133.50, "Tech - eCommerce", "China"),
    ("BAC", "Bank of America", 88, 26.50, "Banking", "US"),
    ("CRM", "Salesforce", 15, 287.00, "Tech - SaaS", "US"),
    ("FIG", "Simplify Exchange Traded Funds", 650, 29.00, "ETF - Alt", "US"),
    ("GS", "Goldman Sachs", 13, 242.50, "Banking", "US"),
    ("JPM", "JPMorgan Chase", 80, 108.00, "Banking", "US"),
    ("RBRK", "Rubrik", 245, 68.00, "Cybersecurity", "US"),
    ("RDDT", "Reddit", 150, 139.00, "Tech - Social", "US"),
    ("TOST", "Toast", 800, 36.00, "Fintech", "US"),
    ("MC.PA", "LVMH Moet Hennessy", 60, 820.00, "Luxury", "France"),
]


def seed():
    conn = sqlite3.connect(DB_PATH)

    # Create tables if they don't exist
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

    # Add columns if they don't exist
    for col, default in [
        ("sector", "''"),
        ("country", "''"),
        ("portfolio_name", "''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE holdings ADD COLUMN {col} TEXT DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    # Clear existing holdings (fresh seed)
    conn.execute("DELETE FROM holdings")

    for ticker, name, shares, avg_cost, sector, country in HOLDINGS:
        total_invested = shares * avg_cost
        conn.execute(
            """INSERT OR REPLACE INTO holdings
               (ticker, name, exchange, quantity, avg_cost, total_invested, sector, country, portfolio_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, name, "", shares, avg_cost, total_invested, sector, country, PORTFOLIO_NAME),
        )
        print(f"  Seeded {ticker:8s} — {shares:>5d} shares @ ${avg_cost:.2f} = ${total_invested:>10,.2f}  [{sector}]")

    conn.commit()

    # Summary
    row = conn.execute("SELECT COUNT(*), SUM(total_invested) FROM holdings").fetchone()
    print(f"\nSeeded {row[0]} holdings, total invested: ${row[1]:,.2f}")
    print(f"Portfolio: {PORTFOLIO_NAME}")

    conn.close()


if __name__ == "__main__":
    seed()
