from __future__ import annotations

import psycopg

_INSERT_SQL = """
INSERT INTO quote_records (
    route, cargo_description, quantity, freight_rate, commission_rate,
    market_benchmark, shipowner_asking_tce, tce, profit_margin_pct, decision,
    quote_input_snapshot, deal_decision_snapshot, reverse_quote_snapshot
) VALUES (
    %(route)s, %(cargo_description)s, %(quantity)s, %(freight_rate)s, %(commission_rate)s,
    %(market_benchmark)s, %(shipowner_asking_tce)s, %(tce)s, %(profit_margin_pct)s, %(decision)s,
    %(quote_input_snapshot)s, %(deal_decision_snapshot)s, %(reverse_quote_snapshot)s
)
"""


def insert_quote_record(database_url: str, row: dict) -> None:
    """Raw DB I/O — INSERT one row into quote_records. Raises on failure; no error handling here."""
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(_INSERT_SQL, row)
        conn.commit()
