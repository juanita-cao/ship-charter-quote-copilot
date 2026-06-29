"""
run_quotation_sandbox — Quotation Side bidirectional rate<->TCE sandbox
(design_frontend.md, Quotation Side redesign).

Composes only already-approved primitives (D2 reverse direction, E2 forward
direction on a perturbed input, D1 for the decision) — invents no new
business rule, per Primitive Integrity.
"""

from __future__ import annotations

import pytest

from src.backend.d_nodes import analyze_deal, reverse_quote
from src.backend.e_nodes import calculate_tce, copy_quote_input_validated
from src.backend.pipeline import run_quotation_sandbox
from src.backend.schemas import DealDecision, QuoteInput


def _valid_inputs(**overrides) -> QuoteInput:
    base = dict(
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
    base.update(overrides)
    return QuoteInput(**base)


def test_target_tce_direction_resolves_rate_via_d2():
    inputs = _valid_inputs()
    result = run_quotation_sandbox(inputs, target_tce=3000.0)

    expected_reverse = reverse_quote(inputs, 3000.0)
    assert result.resolved_freight_rate == expected_reverse.minimum_safe_rate
    assert result.resolved_tce == pytest.approx(3000.0)
    assert result.break_even_rate == expected_reverse.break_even_rate
    assert isinstance(result.decision, DealDecision)


def test_sandbox_freight_rate_direction_resolves_tce_via_e2():
    inputs = _valid_inputs()
    result = run_quotation_sandbox(inputs, sandbox_freight_rate=8.15)

    expected_inputs = copy_quote_input_validated(inputs, {"freight_rate": 8.15})
    expected_tce_result = calculate_tce(expected_inputs)
    assert result.resolved_freight_rate == 8.15
    assert result.resolved_tce == expected_tce_result.tce
    assert isinstance(result.decision, DealDecision)


def test_decision_reuses_d1_not_reinvented():
    inputs = _valid_inputs()
    result = run_quotation_sandbox(inputs, sandbox_freight_rate=8.15)

    sandbox_inputs = copy_quote_input_validated(
        inputs, {"freight_rate": result.resolved_freight_rate}
    )
    expected_decision = analyze_deal(calculate_tce(sandbox_inputs), sandbox_inputs)
    assert result.decision.decision == expected_decision.decision
    assert result.decision.profit_margin_pct == expected_decision.profit_margin_pct


def test_break_even_rate_is_direction_independent():
    """break_even_rate depends only on cost structure, not on which direction
    drove the sandbox — both directions anchored to the same underlying quote
    must agree."""
    inputs = _valid_inputs()
    result_via_tce = run_quotation_sandbox(inputs, target_tce=3000.0)
    result_via_rate = run_quotation_sandbox(inputs, sandbox_freight_rate=8.15)
    assert result_via_tce.break_even_rate == result_via_rate.break_even_rate


def test_sandbox_shipowner_ask_override_moves_break_even_rate_and_margin():
    """ADR-012 bug fix: editing the sandbox's own Shipowner Ask must actually
    move break_even_rate and profit_margin_pct, since both formulas subtract
    shipowner cost — previously the override was only used for the display-only
    spread, never threaded into the inputs analyze_deal/reverse_quote saw."""
    inputs = _valid_inputs(shipowner_asking_tce=2800.0)
    baseline = run_quotation_sandbox(inputs, target_tce=3000.0)
    overridden = run_quotation_sandbox(inputs, target_tce=3000.0, sandbox_shipowner_ask=0.0)
    assert overridden.break_even_rate != baseline.break_even_rate
    assert overridden.decision.profit_margin_pct != baseline.decision.profit_margin_pct

    expected_inputs = copy_quote_input_validated(inputs, {"shipowner_asking_tce": 0.0})
    expected_reverse = reverse_quote(expected_inputs, 3000.0)
    assert overridden.resolved_freight_rate == expected_reverse.minimum_safe_rate
    assert overridden.break_even_rate == expected_reverse.break_even_rate


def test_both_directions_given_raises_value_error():
    inputs = _valid_inputs()
    with pytest.raises(ValueError):
        run_quotation_sandbox(inputs, target_tce=3000.0, sandbox_freight_rate=8.15)


def test_neither_direction_given_raises_value_error():
    inputs = _valid_inputs()
    with pytest.raises(ValueError):
        run_quotation_sandbox(inputs)


def test_commission_rate_100_hard_fails_in_either_direction():
    inputs = _valid_inputs(commission_rate=100.0)
    with pytest.raises(ValueError):
        run_quotation_sandbox(inputs, target_tce=3000.0)
    with pytest.raises(ValueError):
        run_quotation_sandbox(inputs, sandbox_freight_rate=8.15)
