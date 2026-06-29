"""
E2 · calculate_tce — scenarios E2-S01–S03 (design_backend.md §7.4).
"""

from __future__ import annotations

import math

import pytest

from src.backend.e_nodes import calculate_tce, safe_div
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


def test_e2_s01_normal_path_total_days_positive_and_tce_finite():
    result = calculate_tce(_standard_input())
    assert isinstance(result, TCEResult)
    assert result.total_days > 0
    assert math.isfinite(result.tce)


def test_e2_s01_voyage_days_formula():
    inp = _standard_input()
    result = calculate_tce(inp)
    sea_days = (
        inp.ballast_distance / inp.ballast_speed / 24 + inp.laden_distance / inp.laden_speed / 24
    )
    port_days = inp.loading_days + inp.discharging_days + inp.margin_days
    assert result.total_days == sea_days + port_days


def test_e2_s02_boundary_very_slow_speed_no_exception():
    inp = _standard_input(ballast_speed=0.01, laden_speed=0.01)
    result = calculate_tce(inp)
    assert result.total_days > 1000
    assert math.isfinite(result.tce)


def test_e2_s03_zero_total_days_raises_value_error():
    inp = _standard_input(
        ballast_distance=0,
        laden_distance=0,
        loading_days=0,
        discharging_days=0,
        margin_days=0,
    )
    with pytest.raises(ValueError, match="total_days must be positive"):
        calculate_tce(inp)


def test_safe_div_zero_denominator_returns_zero():
    assert safe_div(100, 0) == 0.0


def test_e2_s01_commission_applied_to_gross_freight_revenue():
    inp = _standard_input(quantity=10000.0, freight_rate=20.0, commission_rate=10.0)
    result = calculate_tce(inp)
    freight_revenue = 10000.0 * 20.0
    commission = freight_revenue * 10.0 / 100
    net_freight_income = freight_revenue - commission
    assert result.net_voyage_income == net_freight_income - result.total_voyage_cost


def test_e2_ballast_and_laden_bunker_rates_apply_to_their_own_leg_days():
    """Ballast/laden consumption rates must weight by their own leg's days,
    not get averaged or applied to total sea days (the client's spreadsheet
    tracks these as genuinely different rates)."""
    inp = _standard_input(
        hfo_ballast_consumption=30.0,
        hfo_laden_consumption=10.0,
        mgo_ballast_consumption=2.0,
        mgo_laden_consumption=0.5,
    )
    result = calculate_tce(inp)

    ballast_days = inp.ballast_distance / inp.ballast_speed / 24
    laden_days = inp.laden_distance / inp.laden_speed / 24
    port_days = inp.loading_days + inp.discharging_days + inp.margin_days

    expected_hfo_cost = (
        inp.hfo_ballast_consumption * ballast_days
        + inp.hfo_laden_consumption * laden_days
        + inp.hfo_port_consumption * port_days
    ) * inp.hfo_price
    expected_mgo_cost = (
        inp.mgo_ballast_consumption * ballast_days
        + inp.mgo_laden_consumption * laden_days
        + inp.mgo_port_consumption * port_days
    ) * inp.mgo_price
    expected_bunker_cost = expected_hfo_cost + expected_mgo_cost

    expected_total_voyage_cost = (
        expected_bunker_cost
        + inp.port_cost
        + inp.loading_cost
        + inp.discharging_cost
        + inp.cev_cost
        + inp.ilohc_cost
    )
    assert result.total_voyage_cost == expected_total_voyage_cost
