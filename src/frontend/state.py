from __future__ import annotations

from typing import Any, Literal, NamedTuple

from pydantic import BaseModel


class StateTransitionResult(NamedTuple):
    next_state: str
    session_state_patch: dict[str, Any]


class QuoteSessionState(BaseModel):
    """design_frontend.md Artifact 2 — Session State Contract."""

    save_status: Literal["idle", "saved", "save_failed"] = "idle"

    sandbox_target_tce: float | None = None
    sandbox_freight_rate: float | None = None
    sandbox_shipowner_ask: float | None = None
    sandbox_last_edited: Literal["target_tce", "freight_rate"] | None = None

    view: Literal["welcome", "workspace"] = "welcome"

    # One-way unlock, not a staleness flag (2026-06-28 revision): once the OP
    # has clicked "Run" successfully once this session, every panel goes
    # back to live recompute on every Input edit, same as before the Run
    # gate existed — they never need to click Run again unless "↺ Reset All"
    # sets this back to False.
    has_run: bool = False

    # Set by "↺ Reset All" — makes _render_input_panel() pass value=None/""
    # instead of the sample-voyage default the next time each (popped) input
    # widget is (re)created. Sticky for the rest of the session: once the OP
    # fills in a real value, that key owns its own session_state entry and
    # `value=` is ignored for it anyway, so this flag only ever matters for
    # whichever fields are still untouched.
    inputs_blanked: bool = False


def transition_save_state(
    current_state: str, event: str, run_save_result: bool | None = None
) -> StateTransitionResult:
    """F-State · Select — pure save_status FSM transition (Artifact 1 & 3).

    UI control flow only, not a business decision. Raises on any
    (state, event) combination not in the approved transition table.
    """
    match (current_state, event, run_save_result):
        case (("idle" | "saved" | "save_failed"), "save_clicked", True):
            return StateTransitionResult("saved", {"save_status": "saved"})
        case (("idle" | "saved" | "save_failed"), "save_clicked", False):
            return StateTransitionResult("save_failed", {"save_status": "save_failed"})
        case (("saved" | "save_failed"), "input_changed", None):
            return StateTransitionResult("idle", {"save_status": "idle"})
        case ("idle", "input_changed", None):
            return StateTransitionResult("idle", {})
        case _:
            raise ValueError(f"Unrecognised (state={current_state!r}, event={event!r})")
