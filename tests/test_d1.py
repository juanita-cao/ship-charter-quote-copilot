"""
D1 · analyze_deal — scenarios D1-S01–S06 (design_backend.md §7.4).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.d_nodes import analyze_deal
from src.backend.schemas import QuoteInput, TCEResult


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


def _tce_result(net_voyage_income: float, total_days: float = 20.0) -> TCEResult:
    return TCEResult(
        total_days=total_days,
        total_voyage_cost=100000.0,
        net_voyage_income=net_voyage_income,
        tce=net_voyage_income / total_days if total_days else 0.0,
    )


def test_d1_s01_go_when_margin_meets_threshold():
    # shipowner_asking_tce=0.0 isolates the threshold comparison itself from
    # ADR-012's shipowner-cost subtraction, which has its own tests below.
    inp = _standard_input(
        quantity=10000, freight_rate=20, go_threshold_pct=2.5, shipowner_asking_tce=0.0
    )
    freight_revenue = 10000 * 20  # 200000
    net_voyage_income = freight_revenue * 0.05  # 5% margin, above 2.5% threshold
    tce_result = _tce_result(net_voyage_income)
    decision = analyze_deal(tce_result, inp)
    assert decision.decision == "GO"
    assert decision.rule_triggered == "R1"


def test_d1_s02_no_go_when_margin_below_threshold():
    inp = _standard_input(
        quantity=10000, freight_rate=20, go_threshold_pct=2.5, shipowner_asking_tce=0.0
    )
    freight_revenue = 10000 * 20
    net_voyage_income = freight_revenue * 0.01  # 1% margin, below 2.5%
    tce_result = _tce_result(net_voyage_income)
    decision = analyze_deal(tce_result, inp)
    assert decision.decision == "NO-GO"
    assert decision.rule_triggered == "R2"


def test_d1_s03_boundary_equal_threshold_is_go():
    inp = _standard_input(
        quantity=10000, freight_rate=20, go_threshold_pct=2.5, shipowner_asking_tce=0.0
    )
    freight_revenue = 10000 * 20
    net_voyage_income = freight_revenue * 0.025  # exactly 2.5%
    tce_result = _tce_result(net_voyage_income)
    decision = analyze_deal(tce_result, inp)
    assert decision.decision == "GO"


def test_d1_s07_shipowner_cost_subtracted_from_margin():
    """ADR-012: profit_margin_pct nets out the shipowner's hire cost
    (shipowner_asking_tce * total_days) before dividing by freight_revenue —
    the operator's real bottom-line margin, not just the cargo-side margin
    before paying to charter the vessel in."""
    inp = _standard_input(quantity=10000, freight_rate=20, shipowner_asking_tce=2800.0)
    freight_revenue = 10000 * 20
    net_voyage_income = freight_revenue * 0.05  # 5% before shipowner cost
    total_days = 20.0
    tce_result = _tce_result(net_voyage_income, total_days=total_days)
    decision = analyze_deal(tce_result, inp)
    shipowner_cost = inp.shipowner_asking_tce * total_days
    expected_margin = (net_voyage_income - shipowner_cost) / freight_revenue * 100
    assert decision.profit_margin_pct == pytest.approx(expected_margin)
    assert decision.profit_margin_pct < 5.0


def test_d1_s08_shipowner_cost_can_flip_go_to_no_go():
    """Same voyage economics, only shipowner_asking_tce differs — proves the
    decision now actually responds to what's paid to charter the vessel in,
    not just the cargo-side margin (the gap this whole change was about)."""
    inp_cheap = _standard_input(
        quantity=10000, freight_rate=20, go_threshold_pct=2.5, shipowner_asking_tce=0.0
    )
    inp_expensive = _standard_input(
        quantity=10000, freight_rate=20, go_threshold_pct=2.5, shipowner_asking_tce=2800.0
    )
    freight_revenue = 10000 * 20
    net_voyage_income = freight_revenue * 0.03  # 3%, above 2.5% threshold before shipowner cost
    tce_result = _tce_result(net_voyage_income, total_days=20.0)
    decision_cheap = analyze_deal(tce_result, inp_cheap)
    decision_expensive = analyze_deal(tce_result, inp_expensive)
    assert decision_cheap.decision == "GO"
    assert decision_expensive.decision == "NO-GO"


def test_d1_s09_operator_profit_usd_is_net_voyage_income_minus_shipowner_cost():
    """ADR-014: operator_profit_usd is the absolute-dollar version of the same
    numerator profit_margin_pct divides by freight_revenue — what the OP
    actually pockets on this voyage, net of the shipowner's hire cost."""
    inp = _standard_input(shipowner_asking_tce=2800.0)
    total_days = 20.0
    net_voyage_income = 10000.0
    tce_result = _tce_result(net_voyage_income, total_days=total_days)
    decision = analyze_deal(tce_result, inp)
    expected_profit = net_voyage_income - inp.shipowner_asking_tce * total_days
    assert decision.operator_profit_usd == pytest.approx(expected_profit)


def test_d1_s04_zero_freight_revenue_prevented_by_schema():
    """True freight_revenue == 0 cannot occur through a valid QuoteInput —
    quantity > 0 and freight_rate > 0 are both schema-enforced (gt=0)."""
    with pytest.raises(ValidationError):
        _standard_input(quantity=0)
    with pytest.raises(ValidationError):
        _standard_input(freight_rate=0)


def test_d1_s05_audit_completeness():
    inp = _standard_input()
    tce_result = _tce_result(net_voyage_income=10000.0)
    decision = analyze_deal(tce_result, inp)
    assert decision.reason
    assert decision.rule_triggered in ("R1", "R2")
    assert decision.inputs_snapshot == inp
    assert isinstance(decision.profit_margin_pct, float)
    assert isinstance(decision.spread_vs_shipowner_ask, float)
    assert isinstance(decision.spread_vs_market_benchmark, float)


def test_d1_s05_spreads_computed_correctly():
    inp = _standard_input(shipowner_asking_tce=2800.0, market_benchmark=3000.0)
    tce_result = _tce_result(net_voyage_income=10000.0, total_days=20.0)
    decision = analyze_deal(tce_result, inp)
    assert decision.spread_vs_shipowner_ask == tce_result.tce - 2800.0
    assert decision.spread_vs_market_benchmark == tce_result.tce - 3000.0


def test_d1_s06_validation_failure_is_already_caught_at_schema_level():
    """shipowner_asking_tce < 0 / market_benchmark < 0 raise ValidationError at
    QuoteInput construction (ge=0), before analyze_deal ever runs — see test_schemas.py."""
    with pytest.raises(ValidationError):
        _standard_input(shipowner_asking_tce=-1.0)
    with pytest.raises(ValidationError):
        _standard_input(market_benchmark=-1.0)
