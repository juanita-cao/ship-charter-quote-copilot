from __future__ import annotations

from src.backend.e_nodes import calculate_tce, safe_div
from src.backend.schemas import DealDecision, QuoteInput, ReverseQuoteResult, TCEResult


def analyze_deal(tce_result: TCEResult, inputs: QuoteInput) -> DealDecision:
    """D1 · Matching — binary GO/NO-GO gate on profit margin, net of the
    shipowner's hire cost (ADR-001, amended by ADR-012)."""
    freight_revenue = inputs.quantity * inputs.freight_rate
    shipowner_cost = inputs.shipowner_asking_tce * tce_result.total_days
    profit_margin_pct = (
        safe_div(tce_result.net_voyage_income - shipowner_cost, freight_revenue) * 100
    )

    if profit_margin_pct >= inputs.go_threshold_pct:
        decision = "GO"
        rule_triggered = "R1"
        reason = (
            f"Profit margin {profit_margin_pct:.2f}% meets or exceeds the "
            f"{inputs.go_threshold_pct:.2f}% threshold."
        )
    else:
        decision = "NO-GO"
        rule_triggered = "R2"
        reason = (
            f"Profit margin {profit_margin_pct:.2f}% is below the "
            f"{inputs.go_threshold_pct:.2f}% threshold."
        )

    return DealDecision(
        decision=decision,
        reason=reason,
        rule_triggered=rule_triggered,
        profit_margin_pct=profit_margin_pct,
        operator_profit_usd=tce_result.net_voyage_income - shipowner_cost,
        spread_vs_shipowner_ask=tce_result.tce - inputs.shipowner_asking_tce,
        spread_vs_market_benchmark=tce_result.tce - inputs.market_benchmark,
        inputs_snapshot=inputs,
    )


def reverse_quote(inputs: QuoteInput, target_tce: float) -> ReverseQuoteResult:
    """D2 · Pricing — what rate to quote the cargo owner to hit a target TCE.

    Ignores `go_threshold_pct` entirely — this is purely "what rate hits my own
    target_tce," independent of the company's GO/NO-GO floor used by D1.
    """
    tce_result = calculate_tce(inputs)  # raises ValueError if total_days <= 0
    total_days = tce_result.total_days
    total_voyage_cost = tce_result.total_voyage_cost

    commission_factor = 1 - inputs.commission_rate / 100
    denominator = inputs.quantity * commission_factor

    if denominator <= 0:
        raise ValueError("reverse_quote denominator must be positive")

    # break_even_rate is the rate at which the operator's real profit (net of
    # the shipowner's hire cost) is exactly zero — i.e. TCE == shipowner_asking_tce
    # (ADR-012, kept consistent with D1's shipowner-cost-netted profit_margin_pct).
    shipowner_cost = inputs.shipowner_asking_tce * total_days
    break_even_rate = (total_voyage_cost + shipowner_cost) / denominator

    target_net_voyage_income = target_tce * total_days
    minimum_safe_rate = (target_net_voyage_income + total_voyage_cost) / denominator

    return ReverseQuoteResult(
        break_even_rate=break_even_rate,
        minimum_safe_rate=minimum_safe_rate,
        current_rate=inputs.freight_rate,
    )
