"""
E4 · save_quote_record — scenarios E4-S01–S03 (design_backend.md §7.4).

Unit tests mock the DB boundary (src.backend.db_results.insert_quote_record) —
no real database connection is required (Section 23a, Side-Effect Boundary).
"""

from __future__ import annotations

from unittest.mock import patch

from src.backend.d_nodes import analyze_deal, reverse_quote
from src.backend.e_nodes import calculate_tce, save_quote_record
from src.backend.schemas import QuoteInput


def _standard_input(**overrides) -> QuoteInput:
    kwargs = dict(
        route="CN-JP",
        cargo_description="bulk grain",
        quantity=10000.0,
        freight_rate=20.0,
        commission_rate=2.5,
        loading_days=1.0,
        discharging_days=1.0,
        margin_days=1.0,
        ballast_distance=480.0,
        laden_distance=480.0,
        ballast_speed=12.0,
        laden_speed=12.0,
        hfo_price=600.0,
        mgo_price=900.0,
        hfo_ballast_consumption=20.0,
        hfo_laden_consumption=20.0,
        mgo_ballast_consumption=1.0,
        mgo_laden_consumption=1.0,
        hfo_port_consumption=2.0,
        mgo_port_consumption=0.5,
        port_cost=5000.0,
        loading_cost=3000.0,
        discharging_cost=3000.0,
        cev_cost=1000.0,
        ilohc_cost=500.0,
        market_benchmark=3000.0,
        shipowner_asking_tce=2800.0,
        go_threshold_pct=2.5,
    )
    kwargs.update(overrides)
    return QuoteInput(**kwargs)


def test_e4_s01_normal_path_inserts_row_and_returns_true(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    inp = _standard_input()
    tce_result = calculate_tce(inp)
    decision = analyze_deal(tce_result, inp)
    reverse = reverse_quote(inp, target_tce=3000.0)

    with patch("src.backend.db_results.insert_quote_record") as mock_insert:
        result = save_quote_record(inp, tce_result, decision, reverse)

    assert result is True
    mock_insert.assert_called_once()
    _, row = mock_insert.call_args[0]
    assert row["route"] == "CN-JP"
    assert row["reverse_quote_snapshot"] is not None


def test_e4_s02_optional_reverse_quote_none_gives_null_column(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    inp = _standard_input()
    tce_result = calculate_tce(inp)
    decision = analyze_deal(tce_result, inp)

    with patch("src.backend.db_results.insert_quote_record") as mock_insert:
        result = save_quote_record(inp, tce_result, decision, reverse=None)

    assert result is True
    _, row = mock_insert.call_args[0]
    assert row["reverse_quote_snapshot"] is None


def test_e4_s03_db_failure_soft_fallback_returns_false(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    inp = _standard_input()
    tce_result = calculate_tce(inp)
    decision = analyze_deal(tce_result, inp)

    with patch(
        "src.backend.db_results.insert_quote_record", side_effect=ConnectionError("db down")
    ):
        result = save_quote_record(inp, tce_result, decision, reverse=None)

    assert result is False  # no exception propagates; already-computed results unaffected


def test_e4_s03b_missing_database_url_soft_fallback_returns_false(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    inp = _standard_input()
    tce_result = calculate_tce(inp)
    decision = analyze_deal(tce_result, inp)

    result = save_quote_record(inp, tce_result, decision, reverse=None)

    assert result is False  # KeyError caught by the same SOFT fallback, not raised
