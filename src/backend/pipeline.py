from __future__ import annotations

from src.backend.d_nodes import analyze_deal, reverse_quote
from src.backend.e_nodes import (
    build_risk_scenarios,
    calculate_tce,
    collect_quote_inputs,
    copy_quote_input_validated,
    save_quote_record,
)
from src.backend.schemas import (
    DealDecision,
    QuotationSandboxResult,
    QuoteInput,
    ReverseQuoteResult,
    RiskScenarioRow,
    TCEResult,
)


def run_core_pipeline(raw_ui_state: dict) -> tuple[QuoteInput, TCEResult, DealDecision]:
    """E1 -> E2 -> D1. The mandatory live-preview path, re-run on every form edit."""
    inputs = collect_quote_inputs(raw_ui_state)
    tce_result = calculate_tce(inputs)
    decision = analyze_deal(tce_result, inputs)
    return inputs, tce_result, decision


def run_reverse_quote(inputs: QuoteInput, target_tce: float) -> ReverseQuoteResult:
    """D2, on demand when the user enters a Target TCE."""
    return reverse_quote(inputs, target_tce)


def run_risk_scenarios(
    inputs: QuoteInput, deltas: dict[str, float] | None = None
) -> list[RiskScenarioRow]:
    """E3, on demand when the user expands Risk Scenario. `deltas` lets the OP
    override any scenario's perturbation magnitude from the UI."""
    return build_risk_scenarios(inputs, deltas)


def run_save(
    inputs: QuoteInput,
    tce_result: TCEResult,
    decision: DealDecision,
    reverse: ReverseQuoteResult | None,
) -> bool:
    """E4, only on explicit 'Save Quote' — the only DB write in the pipeline."""
    return save_quote_record(inputs, tce_result, decision, reverse)


def run_quotation_sandbox(
    inputs: QuoteInput,
    target_tce: float | None = None,
    sandbox_freight_rate: float | None = None,
    sandbox_shipowner_ask: float | None = None,
) -> QuotationSandboxResult:
    """Quotation Side sandbox — bidirectional rate<->TCE solve.

    Exactly one of target_tce / sandbox_freight_rate must be given; the other
    is derived. Reuses D2 (target_tce given) or E2 on a perturbed input
    (sandbox_freight_rate given), then D1 for the decision — invents no new
    business rule (Primitive Integrity).

    `sandbox_shipowner_ask`, when given, overrides `inputs.shipowner_asking_tce`
    for every formula below — break_even_rate and the decision's profit_margin_pct
    both depend on it post-ADR-012, so editing this sandbox field must actually
    move those numbers, not just the display-only spread shown elsewhere.
    """
    if (target_tce is None) == (sandbox_freight_rate is None):
        raise ValueError("exactly one of target_tce or sandbox_freight_rate must be given")

    effective_inputs = (
        inputs
        if sandbox_shipowner_ask is None
        else copy_quote_input_validated(inputs, {"shipowner_asking_tce": sandbox_shipowner_ask})
    )

    if target_tce is not None:
        resolved_rate = reverse_quote(effective_inputs, target_tce).minimum_safe_rate
    else:
        resolved_rate = sandbox_freight_rate

    sandbox_inputs = copy_quote_input_validated(effective_inputs, {"freight_rate": resolved_rate})
    tce_result = calculate_tce(sandbox_inputs)
    decision = analyze_deal(tce_result, sandbox_inputs)
    break_even_rate = reverse_quote(effective_inputs, tce_result.tce).break_even_rate

    return QuotationSandboxResult(
        resolved_freight_rate=resolved_rate,
        resolved_tce=tce_result.tce,
        break_even_rate=break_even_rate,
        decision=decision,
    )
