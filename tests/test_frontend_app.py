"""
_missing_field_labels — pure helper mapping a QuoteInput ValidationError to
bilingual Input-panel labels for the page-level fallback banner
(design_frontend.md Artifact 8). Most commonly triggered right after
"↺ Reset All" blanks every field.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.backend.schemas import QuoteInput
from src.frontend.app_streamlit import _missing_field_labels

_VALID_KWARGS = dict(
    route="SHANGHAI-INCHON-OSAKA",
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
    shipowner_asking_tce=2800.0,
    market_benchmark=3000.0,
    go_threshold_pct=2.5,
)


def _validation_error(**overrides) -> ValidationError:
    kwargs = dict(_VALID_KWARGS, **overrides)
    with pytest.raises(ValidationError) as exc_info:
        QuoteInput(**kwargs)
    return exc_info.value


def test_missing_field_labels_single_field():
    exc = _validation_error(quantity=None)
    assert _missing_field_labels(exc) == ["Quantity (RT) · 货物数量"]


def test_missing_field_labels_multiple_fields_sorted():
    exc = _validation_error(quantity=None, freight_rate=None)
    labels = _missing_field_labels(exc)
    assert labels == sorted(labels)
    assert "Quantity (RT) · 货物数量" in labels
    assert "Freight Rate (USD/RT) · 单吨运费" in labels


def test_missing_field_labels_all_21_numeric_fields_blank():
    overrides = {name: None for name, value in _VALID_KWARGS.items() if isinstance(value, float)}
    exc = _validation_error(**overrides)
    assert len(_missing_field_labels(exc)) == len(overrides)
