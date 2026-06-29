"""
Schema / contract tests for schemas.py.

Verifies Pydantic model field constraints match design_backend.md §7.1-7.2.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.schemas import (
    DealDecision,
    QuoteInput,
    ReverseQuoteResult,
    RiskScenarioRow,
    TCEResult,
)


def _valid_quote_input_kwargs() -> dict:
    return dict(
        route="CN-JP",
        cargo_description="bulk grain",
        quantity=10000.0,
        freight_rate=20.0,
        commission_rate=2.5,
        loading_days=1.0,
        discharging_days=1.0,
        margin_days=1.0,
        ballast_distance=500.0,
        laden_distance=800.0,
        ballast_speed=12.0,
        laden_speed=11.0,
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


class TestQuoteInput:
    def test_valid_construction(self):
        q = QuoteInput(**_valid_quote_input_kwargs())
        assert q.quantity == 10000.0
        assert q.go_threshold_pct == 2.5

    @pytest.mark.parametrize(
        "field,bad_value",
        [
            ("quantity", 0),
            ("quantity", -1),
            ("freight_rate", 0),
            ("ballast_speed", 0),
            ("laden_speed", 0),
        ],
    )
    def test_gt_zero_fields_reject_non_positive(self, field, bad_value):
        kwargs = _valid_quote_input_kwargs()
        kwargs[field] = bad_value
        with pytest.raises(ValidationError):
            QuoteInput(**kwargs)

    @pytest.mark.parametrize(
        "field,bad_value",
        [
            ("loading_days", -1),
            ("port_cost", -1),
            ("market_benchmark", -1),
            ("shipowner_asking_tce", -1),
            ("hfo_ballast_consumption", -1),
            ("hfo_laden_consumption", -1),
            ("mgo_ballast_consumption", -1),
            ("mgo_laden_consumption", -1),
        ],
    )
    def test_ge_zero_fields_reject_negative(self, field, bad_value):
        kwargs = _valid_quote_input_kwargs()
        kwargs[field] = bad_value
        with pytest.raises(ValidationError):
            QuoteInput(**kwargs)

    @pytest.mark.parametrize("bad_value", [-1, 100.1, 101])
    def test_commission_rate_bounded_0_100(self, bad_value):
        kwargs = _valid_quote_input_kwargs()
        kwargs["commission_rate"] = bad_value
        with pytest.raises(ValidationError):
            QuoteInput(**kwargs)

    @pytest.mark.parametrize("bad_value", [-1, 100.1, 101])
    def test_go_threshold_pct_bounded_0_100(self, bad_value):
        kwargs = _valid_quote_input_kwargs()
        kwargs["go_threshold_pct"] = bad_value
        with pytest.raises(ValidationError):
            QuoteInput(**kwargs)

    def test_no_risk_buffer_or_target_buffer_fields(self):
        """ADR-001/ADR-002: risk_buffer and target_buffer removed entirely."""
        assert "risk_buffer" not in QuoteInput.model_fields
        assert "target_buffer" not in QuoteInput.model_fields


class TestTCEResult:
    def test_valid_construction(self):
        r = TCEResult(
            total_days=20.0, total_voyage_cost=100000.0, net_voyage_income=50000.0, tce=2500.0
        )
        assert r.tce == 2500.0


class TestDealDecision:
    def test_valid_construction_and_literal(self):
        d = DealDecision(
            decision="GO",
            reason="margin clears threshold",
            rule_triggered="R1",
            profit_margin_pct=3.0,
            operator_profit_usd=6000.0,
            spread_vs_shipowner_ask=200.0,
            spread_vs_market_benchmark=100.0,
            inputs_snapshot=QuoteInput(**_valid_quote_input_kwargs()),
        )
        assert d.decision == "GO"

    def test_decision_rejects_invalid_literal(self):
        with pytest.raises(ValidationError):
            DealDecision(
                decision="MAYBE",
                reason="x",
                rule_triggered="R1",
                profit_margin_pct=3.0,
                operator_profit_usd=6000.0,
                spread_vs_shipowner_ask=200.0,
                spread_vs_market_benchmark=100.0,
                inputs_snapshot=QuoteInput(**_valid_quote_input_kwargs()),
            )


class TestReverseQuoteResult:
    def test_valid_construction(self):
        r = ReverseQuoteResult(break_even_rate=18.0, minimum_safe_rate=18.5, current_rate=20.0)
        assert r.minimum_safe_rate == 18.5

    def test_no_aggressive_or_conservative_fields(self):
        """ADR-002: aggressive_quote/conservative_quote removed entirely."""
        assert "aggressive_quote" not in ReverseQuoteResult.model_fields
        assert "conservative_quote" not in ReverseQuoteResult.model_fields


class TestRiskScenarioRow:
    def test_valid_construction(self):
        row = RiskScenarioRow(
            scenario_name="Base Case",
            scenario_name_zh="基准情形",
            delta=None,
            delta_step=1.0,
            delta_unit="",
            estimated_tce=2500.0,
            tce_impact=0.0,
            profit_margin_pct=3.0,
            decision="GO",
        )
        assert row.decision == "GO"
