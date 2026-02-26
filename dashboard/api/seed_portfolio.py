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

# Holdings data: (ticker, name, shares, avg_cost, sector, country, currency)
# avg_cost calculated as: current_price / (1 + broker_gain%/100)
# Prices as of market close 2026-02-21 from yfinance via deployed API.
# MC.PA is priced in EUR on Yahoo Finance; cost basis stored in EUR.
HOLDINGS = [
    # Ticker, Name, Shares, Avg Cost, Sector, Country, Currency
    ("GLD", "SPDR Gold Shares", 500, 365.85, "Commodities", "US", "USD"),
    ("VOO", "Vanguard S&P 500 ETF", 15, 360.38, "ETF - Index", "US", "USD"),
    ("AFRM", "Affirm Holdings", 450, 71.70, "Fintech", "US", "USD"),
    ("ALAB", "Astera Labs", 250, 169.76, "Semiconductors", "US", "USD"),
    ("AMD", "Advanced Micro Devices", 283, 120.90, "Semiconductors", "US", "USD"),
    ("AMZN", "Amazon.com", 200, 205.37, "Tech - Cloud", "US", "USD"),
    ("ASML", "ASML Holding", 30, 686.05, "Semiconductors", "Netherlands", "USD"),
    ("CRDO", "Credo Technology", 15, 72.72, "Semiconductors", "US", "USD"),
    ("CRWV", "CrowdStrike Holdings", 350, 136.74, "Cybersecurity", "US", "USD"),
    ("DUOL", "Duolingo", 290, 252.27, "EdTech", "US", "USD"),
    ("HOOD", "Robinhood Markets", 150, 142.93, "Fintech", "US", "USD"),
    ("IBIT", "iShares Bitcoin Trust", 238, 67.18, "Crypto ETF", "US", "USD"),
    ("META", "Meta Platforms", 100, 589.83, "Tech - Social", "US", "USD"),
    ("MU", "Micron Technology", 100, 416.59, "Semiconductors", "US", "USD"),
    ("NUTX", "Nutex Health", 250, 95.75, "Healthcare", "US", "USD"),
    ("NVDA", "NVIDIA Corporation", 200, 120.36, "Semiconductors", "US", "USD"),
    ("QQQ", "Invesco QQQ Trust", 120, 594.89, "ETF - Nasdaq", "US", "USD"),
    ("TMDX", "TransMedics Group", 150, 142.35, "Healthcare", "US", "USD"),
    ("BABA", "Alibaba Group", 150, 160.48, "Tech - eCommerce", "China", "USD"),
    ("BAC", "Bank of America", 88, 29.60, "Banking", "US", "USD"),
    ("CRM", "Salesforce", 15, 178.99, "Tech - SaaS", "US", "USD"),
    ("FIG", "Simplify Exchange Traded Funds", 650, 49.80, "ETF - Alt", "US", "USD"),
    ("GS", "Goldman Sachs", 13, 342.60, "Banking", "US", "USD"),
    ("JPM", "JPMorgan Chase", 80, 130.53, "Banking", "US", "USD"),
    ("RBRK", "Rubrik", 245, 81.91, "Cybersecurity", "US", "USD"),
    ("RDDT", "Reddit", 150, 209.97, "Tech - Social", "US", "USD"),
    ("TOST", "Toast", 800, 35.30, "Fintech", "US", "USD"),
    ("MC.PA", "LVMH Moet Hennessy", 60, 806.37, "Luxury", "France", "EUR"),
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
        ("currency", "'USD'"),
    ]:
        try:
            conn.execute(f"ALTER TABLE holdings ADD COLUMN {col} TEXT DEFAULT {default}")
        except sqlite3.OperationalError:
            pass

    # Only insert seed holdings that don't already exist (preserve manual additions)
    existing = {row[0] for row in conn.execute("SELECT ticker FROM holdings").fetchall()}

    inserted = 0
    skipped = 0
    for ticker, name, shares, avg_cost, sector, country, currency in HOLDINGS:
        if ticker in existing:
            skipped += 1
            print(f"  SKIP   {ticker:8s} — already exists")
            continue
        total_invested = shares * avg_cost
        conn.execute(
            """INSERT INTO holdings
               (ticker, name, exchange, quantity, avg_cost, total_invested, sector, country, portfolio_name, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ticker, name, "", shares, avg_cost, total_invested, sector, country, PORTFOLIO_NAME, currency),
        )
        sym = "€" if currency == "EUR" else "$"
        print(f"  Seeded {ticker:8s} — {shares:>5d} shares @ {sym}{avg_cost:.2f} = {sym}{total_invested:>10,.2f}  [{sector}]")
        inserted += 1
    print(f"\n  Inserted: {inserted}, Skipped (already exist): {skipped}")

    conn.commit()

    # Summary
    row = conn.execute("SELECT COUNT(*), SUM(total_invested) FROM holdings").fetchone()
    print(f"\nSeeded {row[0]} holdings, total invested: ${row[1]:,.2f}")
    print(f"Portfolio: {PORTFOLIO_NAME}")

    conn.close()


if __name__ == "__main__":
    seed()
