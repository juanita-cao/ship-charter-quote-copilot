"""
D2 · reverse_quote — scenarios D2-S01–S06 (design_backend.md §7.4).
"""

from __future__ import annotations

import pytest

from src.backend.d_nodes import reverse_quote
from src.backend.schemas import QuoteInput, ReverseQuoteResult


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


def test_d2_s01_normal_path_returns_reverse_quote_result():
    inp = _standard_input()
    result = reverse_quote(inp, target_tce=3000.0)
    assert isinstance(result, ReverseQuoteResult)


def test_d2_s02_rate_ordering():
    inp = _standard_input()
    result = reverse_quote(inp, target_tce=3000.0)
    assert result.minimum_safe_rate >= result.break_even_rate


def test_d2_s03_current_rate_echoes_input():
    inp = _standard_input(freight_rate=22.0)
    result = reverse_quote(inp, target_tce=3000.0)
    assert result.current_rate == 22.0


def test_d2_s04_boundary_target_tce_equals_shipowner_ask_equals_break_even():
    """ADR-012: break_even_rate is the rate at which TCE exactly equals
    shipowner_asking_tce (the true zero-profit point net of the shipowner's
    hire cost) — so target_tce == shipowner_asking_tce is the new equivalence
    point, not target_tce == 0 (that was the pre-ADR-012 zero point, which
    ignored the shipowner cost entirely)."""
    inp = _standard_input()
    result = reverse_quote(inp, target_tce=inp.shipowner_asking_tce)
    assert result.break_even_rate >= 0
    assert result.minimum_safe_rate == pytest.approx(result.break_even_rate)


def test_d2_s05_go_threshold_pct_does_not_affect_minimum_safe_rate():
    """D2 ignores the company's go_threshold_pct floor entirely — minimum_safe_rate
    is purely 'what rate hits my own target_tce,' nothing else (corrects ADR-002)."""
    low = _standard_input(go_threshold_pct=0.0)
    high = _standard_input(go_threshold_pct=50.0)
    result_low = reverse_quote(low, target_tce=3000.0)
    result_high = reverse_quote(high, target_tce=3000.0)
    assert result_low.minimum_safe_rate == pytest.approx(result_high.minimum_safe_rate)
    assert result_low.break_even_rate == pytest.approx(result_high.break_even_rate)


def test_d2_s06_failure_zero_duration_voyage_hard_fails():
    inp = _standard_input(
        ballast_distance=0,
        laden_distance=0,
        loading_days=0,
        discharging_days=0,
        margin_days=0,
    )
    with pytest.raises(ValueError):
        reverse_quote(inp, target_tce=3000.0)


def test_d2_s07_commission_rate_100_hard_fails():
    inp = _standard_input(commission_rate=100.0)
    with pytest.raises(ValueError, match="denominator must be positive"):
        reverse_quote(inp, target_tce=3000.0)
