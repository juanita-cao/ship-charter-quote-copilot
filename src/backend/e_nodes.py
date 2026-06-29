from __future__ import annotations

import logging
import os

from src.backend.schemas import (
    DealDecision,
    QuoteInput,
    ReverseQuoteResult,
    RiskScenarioRow,
    TCEResult,
)

logger = logging.getLogger(__name__)


def safe_div(numerator: float, denominator: float) -> float:
    """Divide, returning 0 instead of raising on a zero denominator."""
    return numerator / denominator if denominator else 0.0


def collect_quote_inputs(raw_ui_state: dict) -> QuoteInput:
    """E1 · Extract — validate raw Streamlit form state into QuoteInput."""
    return QuoteInput(**raw_ui_state)


def calculate_tce(inputs: QuoteInput) -> TCEResult:
    """E2 · Transform — voyage days + bunker cost + total voyage cost → tce."""
    ballast_days = inputs.ballast_distance / inputs.ballast_speed / 24
    laden_days = inputs.laden_distance / inputs.laden_speed / 24
    sea_days = ballast_days + laden_days
    port_days = inputs.loading_days + inputs.discharging_days + inputs.margin_days
    total_days = sea_days + port_days

    if total_days <= 0:
        raise ValueError("total_days must be positive")

    hfo_cost = (
        inputs.hfo_ballast_consumption * ballast_days
        + inputs.hfo_laden_consumption * laden_days
        + inputs.hfo_port_consumption * port_days
    ) * inputs.hfo_price
    mgo_cost = (
        inputs.mgo_ballast_consumption * ballast_days
        + inputs.mgo_laden_consumption * laden_days
        + inputs.mgo_port_consumption * port_days
    ) * inputs.mgo_price
    total_bunker_cost = hfo_cost + mgo_cost

    total_voyage_cost = (
        total_bunker_cost
        + inputs.port_cost
        + inputs.loading_cost
        + inputs.discharging_cost
        + inputs.cev_cost
        + inputs.ilohc_cost
    )

    freight_revenue = inputs.quantity * inputs.freight_rate
    commission = freight_revenue * inputs.commission_rate / 100
    net_freight_income = freight_revenue - commission
    net_voyage_income = net_freight_income - total_voyage_cost

    tce = net_voyage_income / total_days  # total_days > 0 guaranteed by the raise above

    return TCEResult(
        total_days=total_days,
        total_voyage_cost=total_voyage_cost,
        net_voyage_income=net_voyage_income,
        tce=tce,
    )


def copy_quote_input_validated(inputs: QuoteInput, update: dict) -> QuoteInput:
    """model_copy(update=...) skips validation (Pydantic v2 docs) — re-validate explicitly
    so a perturbed scenario can't silently carry an out-of-range field (e.g. freight_rate <= 0)."""
    return QuoteInput.model_validate({**inputs.model_dump(), **update})


# key -> (display name, zh name, default delta, UI step size, display unit).
# Keys are stable identifiers a caller can target with an override delta —
# decoupled from the display name on purpose, since the display name no
# longer embeds the delta magnitude (the OP edits it separately in the UI).
_RISK_SCENARIO_DEFAULTS: dict[str, tuple[str, str, float, float, str]] = {
    "port_cost": ("Port Cost", "港口使费", 5000.0, 500.0, "USD"),
    "bunker_price": ("Bunker Price", "燃油价格", 10.0, 1.0, "%"),
    "margin_days": ("Margin Days", "富余天数", 1.0, 1.0, "day"),
    "freight_rate": ("Freight Rate", "单吨运费", -2.0, 1.0, "USD/RT"),
}


def _apply_risk_delta(inputs: QuoteInput, key: str, delta: float) -> QuoteInput:
    if key == "port_cost":
        return copy_quote_input_validated(inputs, {"port_cost": inputs.port_cost + delta})
    if key == "bunker_price":
        factor = 1 + delta / 100
        return copy_quote_input_validated(
            inputs, {"hfo_price": inputs.hfo_price * factor, "mgo_price": inputs.mgo_price * factor}
        )
    if key == "margin_days":
        return copy_quote_input_validated(inputs, {"margin_days": inputs.margin_days + delta})
    if key == "freight_rate":
        return copy_quote_input_validated(inputs, {"freight_rate": inputs.freight_rate + delta})
    raise ValueError(f"unknown risk scenario key: {key!r}")


def build_risk_scenarios(
    inputs: QuoteInput, deltas: dict[str, float] | None = None
) -> list[RiskScenarioRow]:
    """E3 · Transform — re-run E2+D1 across Base Case + 4 adjustable perturbations.
    No new decision logic. `deltas` lets a caller override any scenario's default
    perturbation magnitude (e.g. from a UI-editable field) by its stable key."""
    from src.backend.d_nodes import (
        analyze_deal,
    )  # local import avoids a circular import with d_nodes

    deltas = deltas or {}
    base_tce = calculate_tce(inputs).tce

    def build_row(
        name: str,
        name_zh: str,
        delta: float | None,
        delta_step: float,
        unit: str,
        row_input: QuoteInput,
    ) -> RiskScenarioRow:
        tce_result = calculate_tce(row_input)
        decision = analyze_deal(tce_result, row_input)
        return RiskScenarioRow(
            scenario_name=name,
            scenario_name_zh=name_zh,
            delta=delta,
            delta_step=delta_step,
            delta_unit=unit,
            estimated_tce=tce_result.tce,
            tce_impact=tce_result.tce - base_tce,
            profit_margin_pct=decision.profit_margin_pct,
            decision=decision.decision,
        )

    rows = [build_row("Base Case", "基准情形", None, 1.0, "", inputs)]
    for key, (name, name_zh, default_delta, step, unit) in _RISK_SCENARIO_DEFAULTS.items():
        delta = deltas.get(key, default_delta)
        rows.append(
            build_row(name, name_zh, delta, step, unit, _apply_risk_delta(inputs, key, delta))
        )
    return rows


def save_quote_record(
    inputs: QuoteInput,
    tce_result: TCEResult,
    decision: DealDecision,
    reverse: ReverseQuoteResult | None,
) -> bool:
    """E4 · eXecute — persist current state as an audit-trail record.

    SOFT error strategy: never raises on a DB failure — logs and returns False
    so the frontend can show a non-blocking warning (ADR-008).
    """
    # Local import (not circularity — none exists here) so tests can patch
    # src.backend.db_results.insert_quote_record without a real DB connection.
    from src.backend.db_results import insert_quote_record

    row = {
        "route": inputs.route,
        "cargo_description": inputs.cargo_description,
        "quantity": inputs.quantity,
        "freight_rate": inputs.freight_rate,
        "commission_rate": inputs.commission_rate,
        "market_benchmark": inputs.market_benchmark,
        "shipowner_asking_tce": inputs.shipowner_asking_tce,
        "tce": tce_result.tce,
        "profit_margin_pct": decision.profit_margin_pct,
        "decision": decision.decision,
        "quote_input_snapshot": inputs.model_dump_json(),
        "deal_decision_snapshot": decision.model_dump_json(),
        "reverse_quote_snapshot": reverse.model_dump_json() if reverse is not None else None,
    }

    try:
        database_url = os.environ["DATABASE_URL"]
        insert_quote_record(database_url, row)
        return True
    except Exception:
        logger.exception("Failed to save quote record")
        return False
