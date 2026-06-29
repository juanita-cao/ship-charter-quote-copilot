from __future__ import annotations

from pydantic import BaseModel

from src.backend.schemas import (
    DealDecision,
    QuotationSandboxResult,
    QuoteInput,
    RiskScenarioRow,
    TCEResult,
)


class QuoteViewModel(BaseModel):
    """design_frontend.md Artifact 6 — ViewModel Contract."""

    # TCE side
    freight_revenue: float
    tce: float
    decision: str
    profit_margin_pct: float
    operator_profit_usd: float
    shipowner_asking_tce: float
    spread_vs_shipowner_ask: float
    owner_side_negative_spread: bool
    # spread_vs_market_benchmark intentionally omitted — D1 computes it, not rendered this version

    # Quotation side sandbox — all None/False until the app's seeding step has run once
    quotation_freight_rate: float | None = None
    quotation_tce: float | None = None
    quotation_freight_revenue: float | None = None
    quotation_break_even_rate: float | None = None
    quotation_decision: str | None = None
    quotation_profit_margin_pct: float | None = None
    quotation_operator_profit_usd: float | None = None
    quotation_shipowner_ask: float | None = None
    quotation_spread_vs_shipowner_ask: float | None = None
    quotation_owner_side_negative_spread: bool = False

    # Risk side — None until the user expands the section
    risk_rows: list[dict] | None = None

    # Save feedback
    save_status: str = "idle"


def build_quote_viewmodel(
    inputs: QuoteInput,
    tce_result: TCEResult,
    decision: DealDecision,
    sandbox_result: QuotationSandboxResult | None = None,
    sandbox_shipowner_ask: float | None = None,
    risk_rows: list[RiskScenarioRow] | None = None,
    save_status: str = "idle",
) -> QuoteViewModel:
    """F-VM · Transform — flatten already-computed backend outputs into one
    render-ready ViewModel. Never calls any backend function itself (Artifact 4
    boundary rule) — sandbox_result is computed by the app layer beforehand."""
    quotation_spread_vs_shipowner_ask = None
    quotation_owner_side_negative_spread = False
    quotation_freight_revenue = None

    if sandbox_result is not None:
        quotation_freight_revenue = inputs.quantity * sandbox_result.resolved_freight_rate
        if sandbox_shipowner_ask is not None:
            quotation_spread_vs_shipowner_ask = sandbox_result.resolved_tce - sandbox_shipowner_ask
            quotation_owner_side_negative_spread = quotation_spread_vs_shipowner_ask < 0

    return QuoteViewModel(
        freight_revenue=inputs.quantity * inputs.freight_rate,
        tce=tce_result.tce,
        decision=decision.decision,
        profit_margin_pct=decision.profit_margin_pct,
        operator_profit_usd=decision.operator_profit_usd,
        shipowner_asking_tce=inputs.shipowner_asking_tce,
        spread_vs_shipowner_ask=decision.spread_vs_shipowner_ask,
        owner_side_negative_spread=decision.spread_vs_shipowner_ask < 0,
        quotation_freight_rate=sandbox_result.resolved_freight_rate if sandbox_result else None,
        quotation_tce=sandbox_result.resolved_tce if sandbox_result else None,
        quotation_freight_revenue=quotation_freight_revenue,
        quotation_break_even_rate=sandbox_result.break_even_rate if sandbox_result else None,
        quotation_decision=sandbox_result.decision.decision if sandbox_result else None,
        quotation_profit_margin_pct=sandbox_result.decision.profit_margin_pct
        if sandbox_result
        else None,
        quotation_operator_profit_usd=sandbox_result.decision.operator_profit_usd
        if sandbox_result
        else None,
        quotation_shipowner_ask=sandbox_shipowner_ask,
        quotation_spread_vs_shipowner_ask=quotation_spread_vs_shipowner_ask,
        quotation_owner_side_negative_spread=quotation_owner_side_negative_spread,
        risk_rows=[row.model_dump() for row in risk_rows] if risk_rows else None,
        save_status=save_status,
    )
