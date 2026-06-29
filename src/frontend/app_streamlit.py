"""
Ship Charter Quote Copilot — Streamlit app.

Step 9: every panel renders off the real backend pipeline (`src.backend.pipeline`),
recomputed from current widget state on every rerun via `_current_vm()`.
"""

from __future__ import annotations

import csv
import io
import sys
from datetime import UTC, datetime
from pathlib import Path

# `streamlit run` adds only this script's own directory (src/frontend/) to
# sys.path, not the project root — so the absolute `src.*` imports below
# would otherwise fail with "No module named 'src'". Bootstrap the project
# root onto sys.path before importing anything under `src`.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_PROJECT_ROOT / ".env")  # populates DATABASE_URL for E4's save_quote_record

import streamlit as st  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from src.backend.d_nodes import reverse_quote  # noqa: E402
from src.backend.pipeline import (  # noqa: E402
    run_core_pipeline,
    run_quotation_sandbox,
    run_risk_scenarios,
    run_save,
)
from src.backend.schemas import (  # noqa: E402
    DealDecision,
    QuoteInput,
    ReverseQuoteResult,
    TCEResult,
)
from src.frontend.state import QuoteSessionState, transition_save_state  # noqa: E402
from src.frontend.view_models import QuoteViewModel, build_quote_viewmodel  # noqa: E402

# Shared Arco Design token palette (same colors used across this author's
# other Streamlit demos for a consistent look). max-width is 1400px here
# (not 100%) since this is a card/form layout, not a map app.
_C_PRIMARY = "#165DFF"
_C_TEXT = "#1d2129"
_C_TEXT_AUX = "#86909c"
_C_BG = "#f2f3f5"
_C_CARD = "#ffffff"
_C_BORDER = "#e5e6eb"
_C_NAVY = "#125993"
_C_GO_BG = "#e8ffea"
_C_GO_FG = "#00B42A"
_C_NOGO_BG = "#ffece8"
_C_NOGO_FG = "#F53F3F"

_CSS = f"""
<style>
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{
    padding-top: 1.5rem !important;
    max-width: 1400px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}}
.stApp {{ background-color: {_C_BG}; color: {_C_TEXT}; }}
h2, h3 {{ color: {_C_NAVY}; font-weight: 600; }}
.cqc-header {{
    background: {_C_NAVY};
    padding: 14px 32px 12px;
    margin: -1.5rem -1rem 1.5rem -1rem;
}}
.cqc-header-title {{
    color: #ffffff !important;
    font-size: 22px;
    font-weight: 600;
    letter-spacing: 0.2px;
    margin: 0;
}}
.cqc-header-sub {{
    color: rgba(255, 255, 255, 0.75) !important;
    font-size: 13px;
    margin: 2px 0 0;
}}
.cqc-section-header {{
    border-bottom: 2px solid {_C_NAVY};
    padding: 0 0 8px;
    margin: 0 0 14px;
}}
.cqc-section-header-title {{
    color: {_C_TEXT} !important;
    font-size: 15px;
    font-weight: 700;
    margin: 0;
}}
.cqc-section-header-sub {{
    color: {_C_TEXT_AUX} !important;
    font-size: 12px;
    margin: 1px 0 0;
}}
.cqc-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 15px;
    font-weight: 700;
}}
.cqc-badge-go {{ background: {_C_GO_BG}; color: {_C_GO_FG}; }}
.cqc-badge-nogo {{ background: {_C_NOGO_BG}; color: {_C_NOGO_FG}; }}
.cqc-badge--sm {{ padding: 2px 10px; font-size: 12px; gap: 4px; }}
.cqc-risk-decision {{ padding-top: 4px; }}
.cqc-badge-cell, .cqc-metric-cell {{
    background: {_C_CARD};
    border: 1px solid {_C_BORDER};
    border-left: 3px solid transparent;
    border-radius: 4px;
    padding: 10px 16px;
    margin-bottom: 10px;
    min-height: 110px;
    box-sizing: border-box;
}}
.cqc-badge-cell--go {{ border-left-color: {_C_GO_FG}; }}
.cqc-badge-cell--nogo {{ border-left-color: {_C_NOGO_FG}; }}
.cqc-metric-cell--hero {{ border-left-color: {_C_NAVY}; }}
.cqc-metric-cell-value {{
    font-size: 22px; font-weight: 600; color: {_C_TEXT}; margin-top: 2px;
}}
.cqc-metric-cell-value--hero {{ font-size: 26px; }}
.cqc-metric-cell--compact {{ min-height: 90px; padding: 8px 5px; }}
.cqc-metric-cell-value--compact {{
    font-size: 14px; font-weight: 700; white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; display: block;
}}
.cqc-num {{
    font-size: 14px; color: {_C_TEXT}; text-align: right; padding-top: 2px;
}}
.cqc-cell-label {{
    font-size: 14px; color: {_C_TEXT_AUX}; font-weight: 600; line-height: 1.25; margin: 0;
}}
.cqc-cell-label-zh {{
    font-size: 11px; color: {_C_TEXT_AUX}; line-height: 1.3; margin: 3px 0 4px;
}}
.cqc-stack-en {{
    font-size: 14px; color: {_C_TEXT_AUX}; font-weight: 600; line-height: 1.25; margin: 0;
}}
.cqc-stack-zh {{ font-size: 11px; color: {_C_TEXT_AUX}; line-height: 1.25; margin: 0; }}
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {{
    color: {_C_TEXT_AUX} !important;
    font-size: 13px !important;
    font-weight: 400 !important;
}}
[data-testid="stWidgetLabel"] p strong,
[data-testid="stWidgetLabel"] label strong {{
    font-weight: 700 !important;
}}
[data-testid="stAlert"] p,
[data-testid="stAlert"] div {{ color: {_C_TEXT} !important; }}
[data-testid="stExpander"] summary p {{
    font-weight: 700 !important;
    font-size: 15px !important;
    color: {_C_TEXT} !important;
}}
[data-testid="stVerticalBlock"]:has(
    > div.element-container
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-risk-table-marker
) [data-testid="stNumberInputField"] {{
    font-size: 14px !important;
    line-height: 22.4px !important;
}}
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-metric-row-marker
) + div[data-testid="stHorizontalBlock"] {{
    gap: 6px !important;
    align-items: center;
}}
/* "Guide"/"↺ Reset All" — both 2-line stacked buttons now (same CSS as
   .cqc-btn-stack-marker), but their labels are different lengths, so they'd
   naturally render at different widths. Force them to the same fixed width
   so the pair looks like one uniform, evenly-spaced toolbar group. */
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-header-controls-marker
) + div[data-testid="stHorizontalBlock"] {{
    align-items: center;
    gap: 6px !important;
    /* Shrink the row to its content's natural width (2 fixed-width
       buttons), then push that whole tight group to the right — instead of
       letting it stretch across the full row and leaving slack inside each
       column, which would put visible empty space *inside* the gap. Mirror
       .cqc-header's own right bleed so the group's right edge lines up
       with the blue header bar's right edge, not the narrower
       block-container content edge. */
    width: fit-content !important;
    margin-left: auto !important;
    margin-right: -1rem !important;
}}
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-header-controls-marker
) + div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {{
    width: 132px !important;
    flex: 0 0 132px !important;
    min-width: 132px !important;
}}
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-header-controls-marker
) + div[data-testid="stHorizontalBlock"] button {{
    width: 132px !important;
}}
button[kind="secondary"] {{
    padding: 4px 14px !important;
    font-size: 13px !important;
    height: auto !important;
}}
button[kind="primary"] {{
    background-color: {_C_PRIMARY} !important;
    border-color: {_C_PRIMARY} !important;
    border-radius: 4px !important;
    height: auto !important;
    padding: 8px 16px !important;
}}
/* Save Quote's two-line label ("English  \n中文") — base style is the
   Chinese second line (small/thin), ::first-line overrides just the
   English line to be bold/larger, matching the metric cards' EN/ZH pattern.
   white-space: nowrap so "Save Quote" never word-wraps into 2 lines at
   narrow widths — a narrower button is fine, a 3-line button isn't. */
[data-testid="stDownloadButton"] button p {{
    font-size: 11px;
    font-weight: 400;
    color: rgba(255, 255, 255, 0.85);
    line-height: 1.5;
    margin: 0;
    white-space: nowrap;
}}
[data-testid="stDownloadButton"] button p::first-line {{
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
}}
/* Same two-line EN-bold-large/ZH-thin-small treatment as Save Quote, for
   plain st.button()s — these all share data-testid="stButton", so each one
   that wants the 2-line look needs its own scoping marker div placed
   immediately before it (same technique as .cqc-metric-row-marker), or this
   would leak onto "↺ Reset All"/"↺ Reset", which must stay single-line. */
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-btn-stack-marker
) + div.element-container [data-testid="stButton"] button p {{
    font-size: 11px;
    font-weight: 400;
    line-height: 1.5;
    margin: 0;
    white-space: nowrap;
}}
div.element-container:has(
    > div[data-testid="stMarkdown"]
    > div[data-testid="stMarkdownContainer"]
    > div.cqc-btn-stack-marker
) + div.element-container [data-testid="stButton"] button p::first-line {{
    font-size: 15px;
    font-weight: 700;
}}
hr {{ border-color: {_C_BORDER}; margin: 10px 0 !important; }}
[data-testid="stVerticalBlock"] {{ gap: 0.6rem; }}
</style>
"""

# Input panel groups (Section 49.3 Input/Better — grouped by category + collapsed).
# (kind, label, key, default, step[, help]) — step omitted for "text" rows.
# Step sizes benchmark against the matching right-side controls (Reverse Quote's
# Target TCE/Freight Rate/Shipowner Ask, Risk Analysis's per-scenario deltas)
# rather than Streamlit's default 0.01 float step, which was too fine-grained
# for these magnitudes.
_INPUT_CATEGORIES: list[tuple[str, bool, list[tuple]]] = [
    (
        "Cargo & Commercial Terms · 货物与商务条款",
        True,
        [
            ("text", "Route", "input_route", "SHANGHAI-INCHON-OSAKA"),
            ("text", "Cargo Description", "input_cargo_description", "Corn"),
            ("number", "Quantity (RT)", "input_quantity", 10000.0, 100.0),
            ("number", "Freight Rate (USD/RT)", "input_freight_rate", 20.0, 1.0),
            ("number", "Commission Rate (%)", "input_commission_rate", 2.5, 0.1),
        ],
    ),
    (
        "Voyage Schedule · 航次日程",
        False,
        [
            ("number", "Loading Days", "input_loading_days", 1.0, 1.0),
            ("number", "Discharging Days", "input_discharging_days", 1.0, 1.0),
            ("number", "Margin Days", "input_margin_days", 1.0, 1.0),
            ("number", "Ballast Distance (nm)", "input_ballast_distance", 480.0, 10.0),
            ("number", "Laden Distance (nm)", "input_laden_distance", 480.0, 10.0),
            ("number", "Ballast Speed (knots)", "input_ballast_speed", 12.0, 0.5),
            ("number", "Laden Speed (knots)", "input_laden_speed", 12.0, 0.5),
        ],
    ),
    (
        "Bunker · 燃油",
        False,
        [
            ("number", "HFO Price", "input_hfo_price", 600.0, 10.0),
            ("number", "MGO Price", "input_mgo_price", 900.0, 10.0),
            ("number", "HFO Ballast Consumption", "input_hfo_ballast_consumption", 20.0, 0.1),
            ("number", "HFO Laden Consumption", "input_hfo_laden_consumption", 20.0, 0.1),
            ("number", "MGO Ballast Consumption", "input_mgo_ballast_consumption", 1.0, 0.05),
            ("number", "MGO Laden Consumption", "input_mgo_laden_consumption", 1.0, 0.05),
            ("number", "HFO Port Consumption", "input_hfo_port_consumption", 2.0, 0.1),
            ("number", "MGO Port Consumption", "input_mgo_port_consumption", 0.5, 0.05),
        ],
    ),
    (
        "Voyage Costs · 航次费用",
        False,
        [
            ("number", "Port Cost", "input_port_cost", 5000.0, 500.0),
            ("number", "Loading Cost", "input_loading_cost", 3000.0, 500.0),
            ("number", "Discharging Cost", "input_discharging_cost", 3000.0, 500.0),
            ("number", "CEV Cost", "input_cev_cost", 1000.0, 100.0),
            ("number", "ILOHC Cost", "input_ilohc_cost", 500.0, 100.0),
        ],
    ),
    (
        "Benchmarks & Threshold · 基准与阈值",
        False,
        [
            ("number", "Shipowner Asking TCE", "input_shipowner_asking_tce", 2800.0, 100.0),
            (
                "number",
                "Market Benchmark",
                "input_market_benchmark",
                3000.0,
                100.0,
                "Collected for backend compatibility; display deferred in this version.",
            ),
            ("number", "GO Threshold (%)", "input_go_threshold_pct", 2.5, 0.1),
        ],
    ),
]


# Bilingual labels — Chinese goes inline after the English label (not on its own
# line below) since 21 fields stacked with a second line each would roughly
# double the Input panel's height.
_ZH_LABELS = {
    "input_route": "航线",
    "input_cargo_description": "货物描述",
    "input_quantity": "货物数量",
    "input_freight_rate": "单吨运费",
    "input_commission_rate": "佣金率",
    "input_loading_days": "装货天数",
    "input_discharging_days": "卸货天数",
    "input_margin_days": "富余天数",
    "input_ballast_distance": "空驶距离",
    "input_laden_distance": "满载距离",
    "input_ballast_speed": "空驶航速",
    "input_laden_speed": "满载航速",
    "input_hfo_price": "重油价格",
    "input_mgo_price": "轻油价格",
    "input_hfo_ballast_consumption": "空驶耗重油",
    "input_hfo_laden_consumption": "满载耗重油",
    "input_mgo_ballast_consumption": "空驶耗轻油",
    "input_mgo_laden_consumption": "满载耗轻油",
    "input_hfo_port_consumption": "在港耗重油",
    "input_mgo_port_consumption": "在港耗轻油",
    "input_port_cost": "港口使费",
    "input_loading_cost": "装货费",
    "input_discharging_cost": "卸货费",
    "input_cev_cost": "CEV 费用",
    "input_ilohc_cost": "ILOHC 费用",
    "input_shipowner_asking_tce": "船东要价 TCE",
    "input_market_benchmark": "市场基准",
    "input_go_threshold_pct": "通过阈值",
}


# Stable keys for the 4 adjustable Risk Analysis rows (Base Case has no
# delta). Mirrors e_nodes._RISK_SCENARIO_DEFAULTS' key order — used to key
# each row's widget and read its current override back on rerun.
_RISK_SCENARIO_KEYS = ["port_cost", "bunker_price", "margin_days", "freight_rate"]


_FIELD_LABEL_BY_NAME: dict[str, str] = {
    field[2].removeprefix("input_"): field[1]
    for _name, _expanded, fields in _INPUT_CATEGORIES
    for field in fields
}


def _init_session_state() -> None:
    if "quote_session" not in st.session_state:
        st.session_state["quote_session"] = QuoteSessionState()


def _collect_raw_ui_state() -> dict:
    raw = {}
    for _name, _expanded, fields in _INPUT_CATEGORIES:
        for field in fields:
            key = field[2]
            raw[key.removeprefix("input_")] = st.session_state[key]
    return raw


def _missing_field_labels(exc: ValidationError) -> list[str]:
    """Map a QuoteInput ValidationError's field names to their bilingual
    Input-panel labels, for the page-level fallback banner (design_frontend.md
    Artifact 8). Most commonly triggered right after "↺ Reset All"."""
    names = {str(error["loc"][0]) for error in exc.errors()}
    labels = []
    for name in names:
        label = _FIELD_LABEL_BY_NAME.get(name, name)
        zh = _ZH_LABELS.get(f"input_{name}")
        labels.append(f"{label} · {zh}" if zh else label)
    return sorted(labels)


def _reset_all() -> None:
    """ "↺ Reset All" — blank every Input field so the OP can replace the
    sample voyage with their own data (design_frontend.md Artifact 2,
    2026-06-28). Pops every input_* key (rather than assigning "" / None
    directly — Streamlit raises if a widget is given both `value=` and a
    programmatic session_state write on the same key) and sets
    `inputs_blanked=True` so _render_input_panel()'s next `value=` for each
    (now-popped) widget is blank instead of the sample-voyage default."""
    for _name, _expanded, fields in _INPUT_CATEGORIES:
        for field in fields:
            st.session_state.pop(field[2], None)
    for widget_key in (
        "sandbox_target_tce_widget",
        "sandbox_freight_rate_widget",
        "sandbox_shipowner_ask_widget",
    ):
        st.session_state.pop(widget_key, None)
    for key in [k for k in st.session_state if k.startswith("risk_delta_")]:
        st.session_state.pop(key, None)
    st.session_state["quote_session"] = QuoteSessionState(view="workspace", inputs_blanked=True)
    st.rerun()


def _current_vm() -> QuoteViewModel:
    session: QuoteSessionState = st.session_state["quote_session"]
    inputs, tce_result, decision = run_core_pipeline(_collect_raw_ui_state())

    sandbox_shipowner_ask = (
        session.sandbox_shipowner_ask
        if session.sandbox_shipowner_ask is not None
        else inputs.shipowner_asking_tce
    )

    if session.sandbox_last_edited == "freight_rate" and session.sandbox_freight_rate is not None:
        sandbox_result = run_quotation_sandbox(
            inputs,
            sandbox_freight_rate=session.sandbox_freight_rate,
            sandbox_shipowner_ask=sandbox_shipowner_ask,
        )
    else:
        target_tce = (
            session.sandbox_target_tce
            if session.sandbox_target_tce is not None
            else tce_result.tce  # first-load seed: open the sandbox coherent with TCE Side
        )
        sandbox_result = run_quotation_sandbox(
            inputs, target_tce=target_tce, sandbox_shipowner_ask=sandbox_shipowner_ask
        )

    risk_deltas = {
        key: st.session_state[f"risk_delta_{key}"]
        for key in _RISK_SCENARIO_KEYS
        if f"risk_delta_{key}" in st.session_state
    }
    risk_rows = run_risk_scenarios(inputs, deltas=risk_deltas or None)

    return build_quote_viewmodel(
        inputs,
        tce_result,
        decision,
        sandbox_result=sandbox_result,
        sandbox_shipowner_ask=sandbox_shipowner_ask,
        risk_rows=risk_rows,
        save_status=session.save_status,
    )


def _section_header(text: str, zh: str) -> None:
    st.markdown(
        f'<div class="cqc-section-header">'
        f'<p class="cqc-section-header-title">{text}</p>'
        f'<p class="cqc-section-header-sub">{zh}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _decision_cell_html(decision: str) -> str:
    """A GO/NO-GO badge rendered as its own metric-box-styled cell, so it sits
    flush with the other KPI cards in a grid row instead of looking oversized.
    Left border is colored by state — the page's one "hero" status signal."""
    is_go = decision == "GO"
    cls = "cqc-badge-go" if is_go else "cqc-badge-nogo"
    cell_cls = "cqc-badge-cell--go" if is_go else "cqc-badge-cell--nogo"
    label = "● GO" if is_go else "● NO-GO"
    return (
        f'<div class="cqc-badge-cell {cell_cls}">'
        '<p class="cqc-cell-label">Decision</p>'
        '<p class="cqc-cell-label-zh">决策</p>'
        f'<span class="cqc-badge {cls}">{label}</span>'
        "</div>"
    )


def _risk_decision_badge_html(decision: str) -> str:
    """Compact version of the same GO/NO-GO badge for a table row — no card
    wrapper, smaller pill, so the Risk Analysis table's rows stay table-height."""
    is_go = decision == "GO"
    cls = "cqc-badge-go" if is_go else "cqc-badge-nogo"
    label = "● GO" if is_go else "● NO-GO"
    return (
        f'<div class="cqc-risk-decision"><span class="cqc-badge cqc-badge--sm {cls}">'
        f"{label}</span></div>"
    )


def _metric_cell_html(en: str, zh: str, value: str, *, hero: bool = False) -> str:
    """KPI card with the Chinese gloss stacked tight under the English label,
    instead of inline (which truncated to '...' in narrow grid columns).
    hero=True marks the one headline number per panel — bigger value, navy
    accent border — so the grid isn't visually flat with every cell equal.
    Non-hero cards default to the compact size — smaller, second-row,
    secondary-info treatment."""
    cell_cls = "cqc-metric-cell--hero" if hero else "cqc-metric-cell--compact"
    value_cls = "cqc-metric-cell-value--hero" if hero else "cqc-metric-cell-value--compact"
    return (
        f'<div class="cqc-metric-cell {cell_cls}">'
        f'<p class="cqc-cell-label">{en}</p>'
        f'<p class="cqc-cell-label-zh">{zh}</p>'
        f'<p class="cqc-metric-cell-value {value_cls}" title="{value}">{value}</p>'
        "</div>"
    )


def _stack_html(en: str, zh: str, *, align: str = "left") -> str:
    """English on top, smaller Chinese gloss directly below — used for Risk
    Analysis' table header and scenario-name cells."""
    style = f' style="text-align:{align}"' if align != "left" else ""
    return f"<div{style}><p class='cqc-stack-en'>{en}</p><p class='cqc-stack-zh'>{zh}</p></div>"


def _num_html(value: str) -> str:
    """Right-aligned numeric cell — financial tables read top-to-bottom by
    magnitude, which only works if the digits line up on the right."""
    return f'<div class="cqc-num">{value}</div>'


def _render_stacked_button(en: str, zh: str, *, key: str, button_type: str = "secondary") -> bool:
    """A 2-line EN-bold-larger / ZH-thin-smaller button label: a
    single-screen demo shouldn't split EN/ZH across separate widgets or
    pages, just stack them in one label, same visual pattern as the metric
    cards' en/zh stack. The marker div scopes the CSS (see _CSS) to just
    this button, so it doesn't leak onto single-line buttons like Reset."""
    st.markdown('<div class="cqc-btn-stack-marker"></div>', unsafe_allow_html=True)
    return st.button(f"{en}  \n{zh}", key=key, type=button_type)


def _render_welcome_screen() -> None:
    """First-load screen explaining the 5-step demo flow (design_frontend.md
    Step 6 / Artifact 1 Page View FSM). English block first, then a fully
    separate Chinese block — no inline EN/ZH mixing within a sentence."""
    session: QuoteSessionState = st.session_state["quote_session"]
    st.markdown(
        """
### Welcome

This is a product demo for a charter-quote calculation tool.

How to use:

1. Input — fill in voyage, cargo, and cost details on the left
2. Estimated TCE — see the equivalent daily rate, GO/NO-GO verdict, and net profit
3. Reverse Quote — solve for a target rate, simulating a negotiation
4. Risk Analysis — see how each cost driver affects the result
5. Save Quote — export the calculation as a CSV

A sample voyage has been pre-filled, so you can view the results immediately.
To try your own case, enter the demo, click "↺ Reset All", fill in your
numbers, and run the calculation.

---

### 欢迎使用

这是一个租船报价测算工具的产品演示。

使用步骤：

1. 输入 — 在左侧填写航次、货物和费用信息
2. 预估 TCE — 查看等价日租金、GO/NO-GO 判断和净利润
3. 反算报价 — 输入目标费率反算，模拟和货主/船东议价
4. 风险分析 — 查看各项成本对结果的影响
5. 保存报价 — 导出本次测算结果为 CSV

系统已预填一个示例航次，进入后可以直接查看计算结果。如果想测试自己的数据，请进入演示后
点击"↺ Reset All"清空示例，再填写参数并运行计算。
        """
    )
    if _render_stacked_button(
        "Enter Demo →", "进入演示", key="enter_demo_btn", button_type="primary"
    ):
        session.view = "workspace"
        st.rerun()


def _render_header_controls() -> None:
    """ "Guide" (back to Welcome) and "↺ Reset All" — top-right of the workspace,
    same fixed width + evenly spaced (see .cqc-header-controls-marker in _CSS)."""
    session: QuoteSessionState = st.session_state["quote_session"]
    st.markdown('<div class="cqc-header-controls-marker"></div>', unsafe_allow_html=True)
    col_help, col_reset = st.columns(2)
    with col_help:
        if _render_stacked_button("Guide", "说明", key="show_welcome_btn"):
            session.view = "welcome"
            st.rerun()
    with col_reset:
        if _render_stacked_button("↺ Reset All", "重置全部", key="reset_all_btn"):
            _reset_all()


def _render_input_panel() -> None:
    _section_header("Input", "输入")
    session: QuoteSessionState = st.session_state["quote_session"]
    for category_name, expanded, fields in _INPUT_CATEGORIES:
        with st.expander(category_name, expanded=expanded):
            for field in fields:
                kind, label, key, sample_default = field[0], field[1], field[2], field[3]
                zh = _ZH_LABELS.get(key)
                full_label = f"**{label}** · {zh}" if zh else label
                # `value=` only matters the first time each (possibly
                # "↺ Reset All"-popped) key is (re)created — Streamlit
                # ignores it for any key that already has a session_state
                # entry, e.g. from the OP's own typing.
                if kind == "text":
                    default = "" if session.inputs_blanked else sample_default
                    st.text_input(full_label, value=default, key=key)
                else:
                    default = None if session.inputs_blanked else sample_default
                    step = field[4]
                    help_text = field[5] if len(field) > 5 else None
                    st.number_input(full_label, value=default, step=step, key=key, help=help_text)


def _render_run_button() -> bool:
    """Bottom of the Input panel — computation only happens on click, not on
    every keystroke (design_frontend.md Artifact 1, 2026-06-28). Returns
    whether it was clicked on this rerun."""
    return _render_stacked_button("Run", "运行", key="run_btn", button_type="primary")


def _render_tce_panel(vm: QuoteViewModel) -> None:
    """Section 49.3 Summarize/Best — Dashboard (KPI cards), the core decision output."""
    _section_header("Estimated TCE", "预估 TCE")
    with st.container(border=True):
        row1 = st.columns(2)
        row1[0].markdown(
            _metric_cell_html("Estimated TCE", "等价日租金 (USD/day)", f"{vm.tce:,.2f}", hero=True),
            unsafe_allow_html=True,
        )
        row1[1].markdown(_decision_cell_html(vm.decision), unsafe_allow_html=True)

        st.markdown('<div class="cqc-metric-row-marker"></div>', unsafe_allow_html=True)
        row2 = st.columns(5)
        row2[0].markdown(
            _metric_cell_html("Revenue", "运费收入", f"{vm.freight_revenue:,.2f}"),
            unsafe_allow_html=True,
        )
        row2[1].markdown(
            _metric_cell_html("Owner Ask", "船东要价", f"{vm.shipowner_asking_tce:,.2f}"),
            unsafe_allow_html=True,
        )
        row2[2].markdown(
            _metric_cell_html("Spread", "价差", f"{vm.spread_vs_shipowner_ask:+,.2f}"),
            unsafe_allow_html=True,
        )
        row2[3].markdown(
            _metric_cell_html("Net Profit", "净利润", f"{vm.operator_profit_usd:+,.2f}"),
            unsafe_allow_html=True,
        )
        row2[4].markdown(
            _metric_cell_html("Margin", "利润率", f"{vm.profit_margin_pct:.2f}%"),
            unsafe_allow_html=True,
        )

        if vm.owner_side_negative_spread:
            st.warning(
                "Owner-side negative spread — not recommended unless there's a strategic reason."
            )


def _render_quotation_panel(vm: QuoteViewModel) -> None:
    """Section 49.3 Adjust/Best — multi-value bidirectional sandbox, negotiation centerpiece."""
    _section_header("Reverse Quote", "反算报价")
    session: QuoteSessionState = st.session_state["quote_session"]

    def _on_target_tce_change() -> None:
        session.sandbox_last_edited = "target_tce"
        session.sandbox_target_tce = st.session_state["sandbox_target_tce_widget"]

    def _on_freight_rate_change() -> None:
        session.sandbox_last_edited = "freight_rate"
        session.sandbox_freight_rate = st.session_state["sandbox_freight_rate_widget"]

    def _on_shipowner_ask_change() -> None:
        session.sandbox_shipowner_ask = st.session_state["sandbox_shipowner_ask_widget"]

    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.number_input(
            "**Target TCE** · 目标 TCE",
            value=float(vm.quotation_tce or 0),
            step=100.0,
            format="%.2f",
            key="sandbox_target_tce_widget",
            on_change=_on_target_tce_change,
        )
        col2.number_input(
            "**Freight Rate** · 单吨运费",
            value=float(vm.quotation_freight_rate or 0),
            step=1.0,
            format="%.2f",
            key="sandbox_freight_rate_widget",
            on_change=_on_freight_rate_change,
        )
        st.number_input(
            "**Shipowner Ask** · 船东要价",
            value=float(vm.quotation_shipowner_ask or 0),
            step=100.0,
            format="%.2f",
            key="sandbox_shipowner_ask_widget",
            on_change=_on_shipowner_ask_change,
        )

        st.divider()
        row1 = st.columns(2)
        row1[0].markdown(
            _metric_cell_html(
                "Break-even Rate",
                "保本运费",
                f"{(vm.quotation_break_even_rate or 0.0):,.2f}",
                hero=True,
            ),
            unsafe_allow_html=True,
        )
        row1[1].markdown(
            _decision_cell_html(vm.quotation_decision or "NO-GO"), unsafe_allow_html=True
        )

        st.markdown('<div class="cqc-metric-row-marker"></div>', unsafe_allow_html=True)
        row2 = st.columns(5)
        row2[0].markdown(
            _metric_cell_html(
                "Revenue", "运费收入", f"{(vm.quotation_freight_revenue or 0.0):,.2f}"
            ),
            unsafe_allow_html=True,
        )
        row2[1].markdown(
            _metric_cell_html(
                "Spread", "价差", f"{(vm.quotation_spread_vs_shipowner_ask or 0.0):+,.2f}"
            ),
            unsafe_allow_html=True,
        )
        row2[2].markdown(
            _metric_cell_html(
                "Net Profit", "净利润", f"{(vm.quotation_operator_profit_usd or 0.0):+,.2f}"
            ),
            unsafe_allow_html=True,
        )
        row2[3].markdown(
            _metric_cell_html(
                "Margin", "利润率", f"{(vm.quotation_profit_margin_pct or 0.0):.2f}%"
            ),
            unsafe_allow_html=True,
        )
        with row2[4]:
            if st.button("↺ Reset"):
                session.sandbox_target_tce = None
                session.sandbox_freight_rate = None
                session.sandbox_shipowner_ask = None
                session.sandbox_last_edited = None
                # Drop the widget-level keys too — a keyed number_input ignores
                # its `value=` arg on rerun once the key already exists, so
                # without this the displayed numbers wouldn't actually reset.
                for widget_key in (
                    "sandbox_target_tce_widget",
                    "sandbox_freight_rate_widget",
                    "sandbox_shipowner_ask_widget",
                ):
                    st.session_state.pop(widget_key, None)
                st.rerun()

        if vm.quotation_owner_side_negative_spread:
            st.warning(
                "Owner-side negative spread — not recommended unless there's a strategic reason."
            )


_RISK_COL_WIDTHS = [1.8, 2.3, 1.2, 1.4, 1.0, 1.3]
_RISK_COL_LABELS = ["Scenario", "Adjust", "Est. TCE", "TCE Impact", "Margin", "Decision"]
_RISK_COL_LABELS_ZH = ["场景", "调整", "预估 TCE", "TCE 变化", "利润率", "决策"]
_RISK_COL_ALIGN = ["left", "left", "right", "right", "right", "left"]


def _render_risk_panel(vm: QuoteViewModel) -> None:
    """No collapsing, no index column — OP can read straight down and tune
    each scenario's delta inline (Section 49.3 Compare/Good — display +
    editable, not a sensitivity matrix)."""
    _section_header("Risk Analysis", "风险分析")
    if not vm.risk_rows:
        return
    with st.container(border=True):
        st.markdown('<div class="cqc-risk-table-marker"></div>', unsafe_allow_html=True)
        header_cols = st.columns(_RISK_COL_WIDTHS)
        for col, en, zh, align in zip(
            header_cols, _RISK_COL_LABELS, _RISK_COL_LABELS_ZH, _RISK_COL_ALIGN, strict=True
        ):
            col.markdown(_stack_html(en, zh, align=align), unsafe_allow_html=True)
        st.divider()
        for i, row in enumerate(vm.risk_rows):
            cols = st.columns(_RISK_COL_WIDTHS)
            cols[0].markdown(
                _stack_html(row["scenario_name"], row["scenario_name_zh"]),
                unsafe_allow_html=True,
            )
            if row["delta"] is None:
                cols[1].write("—")
            else:
                cols[1].number_input(
                    "Adjust",
                    value=int(row["delta"]),
                    step=int(row["delta_step"]),
                    key=f"risk_delta_{_RISK_SCENARIO_KEYS[i - 1]}",
                    label_visibility="collapsed",
                )
            cols[2].markdown(_num_html(f"{row['estimated_tce']:,.2f}"), unsafe_allow_html=True)
            cols[3].markdown(_num_html(f"{row['tce_impact']:+,.2f}"), unsafe_allow_html=True)
            cols[4].markdown(_num_html(f"{row['profit_margin_pct']:.2f}%"), unsafe_allow_html=True)
            cols[5].markdown(_risk_decision_badge_html(row["decision"]), unsafe_allow_html=True)


def _build_quote_csv(
    inputs: QuoteInput,
    tce_result: TCEResult,
    decision: DealDecision,
    reverse: ReverseQuoteResult,
) -> bytes:
    """One-row CSV snapshot for the OP's own local copy — same fields as the
    Supabase audit record, plus the reverse-quote rates. UTF-8 BOM so Excel
    (the OP's native tool) renders Chinese cargo_description correctly."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "route",
            "cargo_description",
            "quantity",
            "freight_rate",
            "commission_rate",
            "market_benchmark",
            "shipowner_asking_tce",
            "tce",
            "profit_margin_pct",
            "decision",
            "break_even_rate",
            "minimum_safe_rate",
        ]
    )
    writer.writerow(
        [
            datetime.now(UTC).isoformat(),
            inputs.route,
            inputs.cargo_description,
            inputs.quantity,
            inputs.freight_rate,
            inputs.commission_rate,
            inputs.market_benchmark,
            inputs.shipowner_asking_tce,
            tce_result.tce,
            decision.profit_margin_pct,
            decision.decision,
            reverse.break_even_rate,
            reverse.minimum_safe_rate,
        ]
    )
    return buffer.getvalue().encode("utf-8-sig")


def _render_save_button(vm: QuoteViewModel) -> None:
    session: QuoteSessionState = st.session_state["quote_session"]
    inputs, tce_result, decision = run_core_pipeline(_collect_raw_ui_state())
    target_tce = (
        session.sandbox_target_tce if session.sandbox_target_tce is not None else tce_result.tce
    )
    reverse = reverse_quote(inputs, target_tce=target_tce)
    csv_bytes = _build_quote_csv(inputs, tce_result, decision, reverse)

    def _on_save_click() -> None:
        run_save_result = run_save(inputs, tce_result, decision, reverse)
        _next_state, patch = transition_save_state(vm.save_status, "save_clicked", run_save_result)
        session.save_status = patch["save_status"]

    col1, col2 = st.columns([1, 3])
    with col1:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        safe_route = (
            "".join(c if c.isalnum() or c in "-_" else "_" for c in inputs.route) or "quote"
        )
        st.download_button(
            "Save Quote  \n保存报价 (CSV)",
            data=csv_bytes,
            file_name=f"quote_{safe_route}_{timestamp}.csv",
            mime="text/csv",
            type="primary",
            on_click=_on_save_click,
        )
    with col2:
        if vm.save_status == "saved":
            st.success("Saved")
        elif vm.save_status == "save_failed":
            st.warning("Save failed — your computed results above are still valid")


def main() -> None:
    st.set_page_config(page_title="Ship Charter Quote Copilot", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="cqc-header">'
        '<p class="cqc-header-title">Ship Charter Quote Copilot</p>'
        '<p class="cqc-header-sub">租船报价助手</p>'
        "</div>",
        unsafe_allow_html=True,
    )
    _init_session_state()
    session: QuoteSessionState = st.session_state["quote_session"]

    if session.view == "welcome":
        _render_welcome_screen()
        return

    _render_header_controls()

    col_input, col_output = st.columns(2)
    with col_input:
        _render_input_panel()
        if not session.has_run and _render_run_button():
            session.has_run = True
            # Without this, the Run button stays drawn for this one render
            # pass (it was already called above before its return value was
            # known) — force a clean rerun so it disappears immediately
            # instead of lingering until the OP's next unrelated edit.
            st.rerun()

    # One-way unlock (2026-06-28 revision): once `has_run` is True, every
    # panel goes back to live recompute on every Input edit — the OP only
    # ever needs to click Run again after "↺ Reset All" resets it to False.
    if not session.has_run:
        with col_output:
            _section_header("Estimated TCE", "预估 TCE")
            st.warning(
                "Fill in the Input fields on the left, then click **Run** "
                "to see the results.\n\n"
                "请先填写左侧的输入字段，填完后点击「Run」查看结果。"
            )
        return

    try:
        vm = _current_vm()
    except ValidationError as exc:
        with col_output:
            _section_header("Estimated TCE", "预估 TCE")
            st.warning(
                "请先完整填写以下字段才能查看结果 / "
                "Fill in the following fields to see results:  \n"
                + "、".join(_missing_field_labels(exc))
            )
        return

    with col_output:
        _render_tce_panel(vm)
        st.divider()
        _render_quotation_panel(vm)
        st.divider()
        _render_risk_panel(vm)
        st.divider()
        _render_save_button(vm)


if __name__ == "__main__":
    main()
