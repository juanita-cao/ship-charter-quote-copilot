"""
E1 · collect_quote_inputs — scenarios E1-S01–S03 (design_backend.md §7.4).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.e_nodes import collect_quote_inputs
from src.backend.schemas import QuoteInput


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


def test_e1_s01_normal_path_returns_complete_quote_input():
    result = collect_quote_inputs(_valid_raw_ui_state())
    assert isinstance(result, QuoteInput)
    assert result.quantity == 10000.0


def test_e1_s02_boundary_quantity_just_above_zero():
    raw = _valid_raw_ui_state()
    raw["quantity"] = 0.01
    result = collect_quote_inputs(raw)
    assert result.quantity == 0.01


@pytest.mark.parametrize(
    "field,bad_value",
    [
        ("quantity", 0),
        ("quantity", -5),
        ("commission_rate", 101),
    ],
)
def test_e1_s03_failure_raises_validation_error(field, bad_value):
    raw = _valid_raw_ui_state()
    raw[field] = bad_value
    with pytest.raises(ValidationError):
        collect_quote_inputs(raw)


def test_e1_s03_failure_missing_required_field():
    raw = _valid_raw_ui_state()
    raw.pop("quantity")
    with pytest.raises(ValidationError):
        collect_quote_inputs(raw)
