"""
F-State · transition_save_state — pure save_status FSM (design_frontend.md
Artifacts 1 & 3). Section 31.7 Rule 1: pure function, returns
StateTransitionResult, raises on any unrecognised (state, event).
"""

from __future__ import annotations

import pytest

from src.frontend.state import StateTransitionResult, transition_save_state


def test_f_state_s01_save_success_from_idle():
    result = transition_save_state("idle", "save_clicked", run_save_result=True)
    assert result == StateTransitionResult("saved", {"save_status": "saved"})


def test_f_state_s02_save_failure_from_idle():
    result = transition_save_state("idle", "save_clicked", run_save_result=False)
    assert result == StateTransitionResult("save_failed", {"save_status": "save_failed"})


def test_f_state_s03_input_changed_resets_saved():
    result = transition_save_state("saved", "input_changed")
    assert result == StateTransitionResult("idle", {"save_status": "idle"})


def test_f_state_s04_input_changed_resets_save_failed():
    result = transition_save_state("save_failed", "input_changed")
    assert result == StateTransitionResult("idle", {"save_status": "idle"})


def test_f_state_s05_input_changed_is_noop_on_idle():
    result = transition_save_state("idle", "input_changed")
    assert result == StateTransitionResult("idle", {})


def test_f_state_s06_unrecognised_combination_hard_fails():
    with pytest.raises(ValueError):
        transition_save_state("idle", "some_unknown_event")


@pytest.mark.parametrize("current_state", ["idle", "saved", "save_failed"])
def test_save_clicked_success_from_any_state(current_state):
    result = transition_save_state(current_state, "save_clicked", run_save_result=True)
    assert result == StateTransitionResult("saved", {"save_status": "saved"})


@pytest.mark.parametrize("current_state", ["idle", "saved", "save_failed"])
def test_save_clicked_failure_from_any_state(current_state):
    result = transition_save_state(current_state, "save_clicked", run_save_result=False)
    assert result == StateTransitionResult("save_failed", {"save_status": "save_failed"})


def test_save_clicked_without_run_save_result_hard_fails():
    with pytest.raises(ValueError):
        transition_save_state("idle", "save_clicked")
