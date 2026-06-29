"""
F-VM · build_quote_viewmodel — pure flattening transform (design_frontend.md
Artifact 6 & 9). Never calls any backend function itself — only flattens
already-computed backend outputs, per the Artifact 4 boundary rule.
"""

from __future__ import annotations

from src.backend.schemas import DealDecision, QuotationSandboxResult, QuoteInput, TCEResult
from src.frontend.view_models import build_quote_viewmodel


def _inputs(**overrides) -> QuoteInput:
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


def _tce_result(**overrides) -> TCEResult:
    base = dict(
        total_days=41.6, total_voyage_cost=33550.0, net_voyage_income=850000.0, tce=20432.69
    )
    base.update(overrides)
    return TCEResult(**base)


def _decision(**overrides) -> DealDecision:
    base = dict(
        decision="GO",
        reason="ok",
        rule_triggered="R1",
        profit_margin_pct=67.27,
        operator_profit_usd=566073.71,
        spread_vs_shipowner_ask=18444.74,
        spread_vs_market_benchmark=18244.74,
        inputs_snapshot=_inputs(),
    )
    base.update(overrides)
    return DealDecision(**base)


def _sandbox_result(**overrides) -> QuotationSandboxResult:
    base = dict(
        resolved_freight_rate=8.15,
        resolved_tce=3000.0,
        break_even_rate=6.20,
        decision=_decision(decision="GO", profit_margin_pct=67.27),
    )
    base.update(overrides)
    return QuotationSandboxResult(**base)


def test_f_vm_s01_sandbox_not_seeded():
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision(), sandbox_result=None)

    assert vm.quotation_freight_rate is None
    assert vm.quotation_tce is None
    assert vm.quotation_freight_revenue is None
    assert vm.quotation_break_even_rate is None
    assert vm.quotation_decision is None
    assert vm.quotation_profit_margin_pct is None
    assert vm.quotation_operator_profit_usd is None
    assert vm.quotation_owner_side_negative_spread is False


def test_f_vm_s02_sandbox_result_flattened():
    sandbox_result = _sandbox_result()
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision(), sandbox_result=sandbox_result)

    assert vm.quotation_freight_rate == sandbox_result.resolved_freight_rate
    assert vm.quotation_tce == sandbox_result.resolved_tce
    assert vm.quotation_break_even_rate == sandbox_result.break_even_rate
    assert vm.quotation_decision == sandbox_result.decision.decision
    assert vm.quotation_profit_margin_pct == sandbox_result.decision.profit_margin_pct
    assert vm.quotation_operator_profit_usd == sandbox_result.decision.operator_profit_usd


def test_f_vm_operator_profit_usd_flattened_from_decision():
    decision = _decision(operator_profit_usd=12345.67)
    vm = build_quote_viewmodel(_inputs(), _tce_result(), decision)
    assert vm.operator_profit_usd == 12345.67


def test_f_vm_s03_quotation_freight_revenue_derived():
    inputs = _inputs(quantity=10000.0)
    sandbox_result = _sandbox_result(resolved_freight_rate=8.15)
    vm = build_quote_viewmodel(inputs, _tce_result(), _decision(), sandbox_result=sandbox_result)

    assert vm.quotation_freight_revenue == 10000.0 * 8.15


def test_f_vm_s04_tce_side_negative_spread_flag():
    decision = _decision(spread_vs_shipowner_ask=-100.0)
    vm = build_quote_viewmodel(_inputs(), _tce_result(), decision)
    assert vm.owner_side_negative_spread is True


def test_f_vm_s05_tce_side_non_negative_spread_flag():
    decision = _decision(spread_vs_shipowner_ask=100.0)
    vm = build_quote_viewmodel(_inputs(), _tce_result(), decision)
    assert vm.owner_side_negative_spread is False


def test_f_vm_s06_quotation_side_negative_spread_flag():
    sandbox_result = _sandbox_result(resolved_tce=2000.0)
    vm = build_quote_viewmodel(
        _inputs(),
        _tce_result(),
        _decision(),
        sandbox_result=sandbox_result,
        sandbox_shipowner_ask=2800.0,
    )
    assert vm.quotation_spread_vs_shipowner_ask == 2000.0 - 2800.0
    assert vm.quotation_owner_side_negative_spread is True


def test_f_vm_s07_quotation_side_non_negative_spread_flag():
    sandbox_result = _sandbox_result(resolved_tce=3000.0)
    vm = build_quote_viewmodel(
        _inputs(),
        _tce_result(),
        _decision(),
        sandbox_result=sandbox_result,
        sandbox_shipowner_ask=2800.0,
    )
    assert vm.quotation_spread_vs_shipowner_ask == 3000.0 - 2800.0
    assert vm.quotation_owner_side_negative_spread is False


def test_f_vm_s08_market_benchmark_never_surfaced():
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision())
    assert not hasattr(vm, "spread_vs_market_benchmark")


def test_freight_revenue_uses_input_freight_rate():
    inputs = _inputs(quantity=10000.0, freight_rate=20.0)
    vm = build_quote_viewmodel(inputs, _tce_result(), _decision())
    assert vm.freight_revenue == 200000.0


def test_risk_rows_passed_through_as_dicts():
    from src.backend.schemas import RiskScenarioRow

    rows = [
        RiskScenarioRow(
            scenario_name="Base Case",
            scenario_name_zh="基准情形",
            delta=None,
            delta_step=1.0,
            delta_unit="",
            estimated_tce=20432.69,
            tce_impact=0.0,
            profit_margin_pct=67.27,
            decision="GO",
        )
    ]
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision(), risk_rows=rows)
    assert vm.risk_rows == [rows[0].model_dump()]


def test_risk_rows_none_when_not_expanded():
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision())
    assert vm.risk_rows is None


def test_save_status_passed_through():
    vm = build_quote_viewmodel(_inputs(), _tce_result(), _decision(), save_status="saved")
    assert vm.save_status == "saved"
