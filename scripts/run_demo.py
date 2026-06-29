"""
CLI smoke-test entry point.

Runs the real pipeline end-to-end on a sample voyage, no mocks, no DB write.
Usage (from project root): python -m scripts.run_demo
"""

from __future__ import annotations

from src.backend.pipeline import run_core_pipeline, run_reverse_quote, run_risk_scenarios

SAMPLE_RAW_UI_STATE = dict(
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


def main() -> None:
    inputs, tce_result, decision = run_core_pipeline(SAMPLE_RAW_UI_STATE)
    print(f"TCE: {tce_result.tce:.2f} USD/day")
    print(f"Decision: {decision.decision} (margin {decision.profit_margin_pct:.2f}%)")
    print(f"Spread vs shipowner ask: {decision.spread_vs_shipowner_ask:.2f}")

    reverse = run_reverse_quote(inputs, target_tce=3000.0)
    print(
        f"Reverse quote — break-even: {reverse.break_even_rate:.2f}, "
        f"min safe: {reverse.minimum_safe_rate:.2f}"
    )

    risk_rows = run_risk_scenarios(inputs)
    print(f"Risk scenarios: {len(risk_rows)} rows, {[r.scenario_name for r in risk_rows]}")


if __name__ == "__main__":
    main()
