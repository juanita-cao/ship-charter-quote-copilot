"""
pipeline.py — integration tests (design_backend.md §10 T9).

Exercises the real cross-node data flow (E1->E2->D1, D2, E3) without mocking
anything except E4's DB write — that's the only node with a real side effect.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.backend.d_nodes import analyze_deal
from src.backend.e_nodes import calculate_tce
from src.backend.pipeline import run_core_pipeline, run_reverse_quote, run_risk_scenarios, run_save
from src.backend.schemas import (
    DealDecision,
    QuoteInput,
    ReverseQuoteResult,
    RiskScenarioRow,
    TCEResult,
)


def _valid_raw_ui_state() -> dict:
    return dict(
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


def test_run_core_pipeline_chains_e1_e2_d1_correctly():
    inputs, tce_result, decision = run_core_pipeline(_valid_raw_ui_state())

    assert isinstance(inputs, QuoteInput)
    assert isinstance(tce_result, TCEResult)
    assert isinstance(decision, DealDecision)

    # Cross-check against independently re-running E2+D1 on the same inputs.
    expected_tce_result = calculate_tce(inputs)
    expected_decision = analyze_deal(expected_tce_result, inputs)
    assert tce_result == expected_tce_result
    assert decision.decision == expected_decision.decision
    assert decision.profit_margin_pct == expected_decision.profit_margin_pct


def test_run_reverse_quote_wraps_d2():
    inputs, _, _ = run_core_pipeline(_valid_raw_ui_state())
    result = run_reverse_quote(inputs, target_tce=3000.0)
    assert isinstance(result, ReverseQuoteResult)
    assert result.minimum_safe_rate >= result.break_even_rate


def test_run_risk_scenarios_wraps_e3():
    inputs, _, _ = run_core_pipeline(_valid_raw_ui_state())
    rows = run_risk_scenarios(inputs)
    assert len(rows) == 5
    assert all(isinstance(row, RiskScenarioRow) for row in rows)


def test_run_risk_scenarios_passes_deltas_through_to_e3():
    inputs, _, _ = run_core_pipeline(_valid_raw_ui_state())
    default_rows = {row.scenario_name: row for row in run_risk_scenarios(inputs)}
    overridden_rows = {
        row.scenario_name: row for row in run_risk_scenarios(inputs, deltas={"port_cost": 9000.0})
    }
    assert overridden_rows["Port Cost"].delta == 9000.0
    assert overridden_rows["Port Cost"].estimated_tce != default_rows["Port Cost"].estimated_tce


def test_run_save_wraps_e4_with_mocked_db(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    inputs, tce_result, decision = run_core_pipeline(_valid_raw_ui_state())
    reverse = run_reverse_quote(inputs, target_tce=3000.0)

    with patch("src.backend.db_results.insert_quote_record") as mock_insert:
        result = run_save(inputs, tce_result, decision, reverse)

    assert result is True
    mock_insert.assert_called_once()


def test_full_user_journey_end_to_end(monkeypatch):
    """Simulates the actual UX: live preview -> optional reverse quote ->
    optional risk scenarios -> explicit save, all on the same input snapshot."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")

    inputs, tce_result, decision = run_core_pipeline(_valid_raw_ui_state())
    assert decision.decision in ("GO", "NO-GO")

    reverse = run_reverse_quote(inputs, target_tce=3000.0)
    assert reverse.current_rate == inputs.freight_rate

    risk_rows = run_risk_scenarios(inputs)
    assert risk_rows[0].scenario_name == "Base Case"

    with patch("src.backend.db_results.insert_quote_record") as mock_insert:
        saved = run_save(inputs, tce_result, decision, reverse)

    assert saved is True
    _, row = mock_insert.call_args[0]
    assert row["reverse_quote_snapshot"] is not None


def test_run_core_pipeline_invalid_raw_input_raises_validation_error():
    raw = _valid_raw_ui_state()
    raw["quantity"] = 0
    with pytest.raises(ValidationError):
        run_core_pipeline(raw)
