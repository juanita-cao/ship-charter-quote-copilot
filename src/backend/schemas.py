from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QuoteInput(BaseModel):
    route: str
    cargo_description: str

    quantity: float = Field(gt=0)  # cargo qty, RT
    freight_rate: float = Field(gt=0)  # USD/RT — quoted to cargo owner
    commission_rate: float = Field(ge=0, le=100)  # %

    loading_days: float = Field(ge=0)
    discharging_days: float = Field(ge=0)
    margin_days: float = Field(ge=0)  # port/weather buffer days

    ballast_distance: float = Field(ge=0)  # nm
    laden_distance: float = Field(ge=0)  # nm
    ballast_speed: float = Field(gt=0)  # knots
    laden_speed: float = Field(gt=0)  # knots

    hfo_price: float = Field(ge=0)
    mgo_price: float = Field(ge=0)
    hfo_ballast_consumption: float = Field(ge=0)
    hfo_laden_consumption: float = Field(ge=0)
    mgo_ballast_consumption: float = Field(ge=0)
    mgo_laden_consumption: float = Field(ge=0)
    hfo_port_consumption: float = Field(ge=0)
    mgo_port_consumption: float = Field(ge=0)

    port_cost: float = Field(ge=0)
    loading_cost: float = Field(ge=0)
    discharging_cost: float = Field(ge=0)
    cev_cost: float = Field(ge=0)
    ilohc_cost: float = Field(ge=0)

    market_benchmark: float = Field(ge=0)  # manual entry — display reference only
    shipowner_asking_tce: float = Field(ge=0)  # manual entry — display reference only
    go_threshold_pct: float = Field(ge=0, le=100)  # company-configurable, pilot: 2.5


class TCEResult(BaseModel):
    total_days: float
    total_voyage_cost: float
    net_voyage_income: float
    tce: float


class DealDecision(BaseModel):
    decision: Literal["GO", "NO-GO"]
    reason: str
    rule_triggered: str  # "R1" (GO) / "R2" (NO-GO)
    profit_margin_pct: float  # drives the decision
    operator_profit_usd: float  # net_voyage_income - shipowner_cost — display only (ADR-014)
    spread_vs_shipowner_ask: float  # tce - shipowner_asking_tce — display only
    spread_vs_market_benchmark: float  # tce - market_benchmark — display only
    inputs_snapshot: QuoteInput


class ReverseQuoteResult(BaseModel):
    break_even_rate: float
    minimum_safe_rate: float  # rate that hits target_tce; independent of go_threshold_pct (ADR-005)
    current_rate: float  # echoes QuoteInput.freight_rate


class QuotationSandboxResult(BaseModel):
    resolved_freight_rate: float
    resolved_tce: float
    break_even_rate: float
    decision: DealDecision


class RiskScenarioRow(BaseModel):
    scenario_name: str
    scenario_name_zh: str
    delta: float | None  # the perturbation applied; None for Base Case
    delta_step: float  # UI number_input step size for this scenario's delta
    delta_unit: str  # display unit, e.g. "USD", "%", "day", "USD/RT"; "" for Base Case
    estimated_tce: float
    tce_impact: float  # estimated_tce - base_tce
    profit_margin_pct: float
    decision: Literal["GO", "NO-GO"]
