"""
E3 · build_risk_scenarios — scenarios E3-S01–S11 (design_backend.md §7.4).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.e_nodes import _RISK_SCENARIO_DEFAULTS, build_risk_scenarios, calculate_tce
from src.backend.schemas import QuoteInput, RiskScenarioRow

EXPECTED_SCENARIO_NAMES = ["Base Case", "Port Cost", "Bunker Price", "Margin Days", "Freight Rate"]


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


def test_e3_s01_normal_path_returns_fixed_five_rows():
    rows = build_risk_scenarios(_standard_input())
    assert len(rows) == 5
    assert all(isinstance(row, RiskScenarioRow) for row in rows)


def test_e3_s02_output_shape():
    rows = build_risk_scenarios(_standard_input())
    for row in rows:
        assert isinstance(row.scenario_name, str)
        assert isinstance(row.scenario_name_zh, str)
        assert isinstance(row.delta_step, float)
        assert isinstance(row.delta_unit, str)
        assert isinstance(row.estimated_tce, float)
        assert isinstance(row.tce_impact, float)
        assert isinstance(row.profit_margin_pct, float)
        assert row.decision in ("GO", "NO-GO")


def test_e3_s03_scenario_coverage():
    rows = build_risk_scenarios(_standard_input())
    assert [row.scenario_name for row in rows] == EXPECTED_SCENARIO_NAMES


def test_e3_s04_impact_formula_relative_to_base_case():
    inp = _standard_input()
    rows = build_risk_scenarios(inp)
    base_tce = calculate_tce(inp).tce
    by_name = {row.scenario_name: row for row in rows}
    assert by_name["Base Case"].tce_impact == 0.0
    for row in rows:
        assert row.tce_impact == row.estimated_tce - base_tce


def test_e3_s05_margin_formula():
    """Freight-rate scenarios change freight_revenue too, so check Base Case directly.
    Margin nets out shipowner_asking_tce * total_days, per ADR-012."""
    inp = _standard_input()
    rows = build_risk_scenarios(inp)
    base_row = next(r for r in rows if r.scenario_name == "Base Case")
    freight_revenue = inp.quantity * inp.freight_rate
    tce_result = calculate_tce(inp)
    shipowner_cost = inp.shipowner_asking_tce * tce_result.total_days
    expected_margin = (tce_result.net_voyage_income - shipowner_cost) / freight_revenue * 100
    assert base_row.profit_margin_pct == expected_margin


def test_e3_s06_out_of_scope_no_new_decision_rule():
    """build_risk_scenarios reuses E2+D1 only — every row's decision matches
    independently re-running analyze_deal on the same perturbed input."""
    from src.backend.d_nodes import analyze_deal

    inp = _standard_input(port_cost=10000.0)
    rows = build_risk_scenarios(inp)
    port_cost_row = next(r for r in rows if r.scenario_name == "Port Cost")
    perturbed = inp.model_copy(update={"port_cost": inp.port_cost + 5000})
    tce_result = calculate_tce(perturbed)
    decision = analyze_deal(tce_result, perturbed)
    assert port_cost_row.decision == decision.decision
    assert port_cost_row.profit_margin_pct == decision.profit_margin_pct


def test_e3_s07_determinism():
    inp = _standard_input()
    rows1 = build_risk_scenarios(inp)
    rows2 = build_risk_scenarios(inp)
    assert rows1 == rows2


def test_e3_s08_freight_rate_minus_2_invalid_when_rate_too_low():
    inp = _standard_input(freight_rate=1.5)
    with pytest.raises(ValidationError):
        build_risk_scenarios(inp)


def test_e3_s09_default_deltas_match_scenario_defaults():
    rows = build_risk_scenarios(_standard_input())
    by_name = {row.scenario_name: row for row in rows}
    for key, (name, name_zh, default_delta, step, unit) in _RISK_SCENARIO_DEFAULTS.items():
        row = by_name[name]
        assert row.scenario_name_zh == name_zh
        assert row.delta == default_delta
        assert row.delta_step == step
        assert row.delta_unit == unit


def test_e3_s10_override_delta_changes_only_targeted_scenario():
    inp = _standard_input()
    default_rows = {row.scenario_name: row for row in build_risk_scenarios(inp)}
    overridden_rows = {
        row.scenario_name: row for row in build_risk_scenarios(inp, deltas={"port_cost": 9000.0})
    }

    assert overridden_rows["Port Cost"].delta == 9000.0
    assert overridden_rows["Port Cost"].estimated_tce != default_rows["Port Cost"].estimated_tce

    for name in ("Base Case", "Bunker Price", "Margin Days", "Freight Rate"):
        assert overridden_rows[name].delta == default_rows[name].delta
        assert overridden_rows[name].estimated_tce == default_rows[name].estimated_tce


def test_e3_s11_base_case_delta_is_none_others_are_not():
    rows = build_risk_scenarios(_standard_input())
    by_name = {row.scenario_name: row for row in rows}
    assert by_name["Base Case"].delta is None
    assert by_name["Base Case"].delta_unit == ""
    for name in ("Port Cost", "Bunker Price", "Margin Days", "Freight Rate"):
        assert by_name[name].delta is not None
