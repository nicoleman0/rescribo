from collections.abc import Callable

import pytest

from feedback.transitions import (
    PROBLEM_TRANSITIONS,
    REPORT_TRANSITIONS,
    InvalidTransition,
    check_problem_transition,
    check_report_transition,
)


@pytest.mark.parametrize(
    ("action", "state", "expected"),
    [
        ("link", "new", "linked"),
        ("link", "linked", "linked"),
        ("unlink", "linked", "new"),
        ("dismiss", "new", "dismissed"),
        ("restore", "dismissed", "new"),
    ],
)
def test_report_transitions(action: str, state: str, expected: str) -> None:
    assert check_report_transition(action=action, from_state=state) == expected


@pytest.mark.parametrize(
    ("action", "state", "expected"),
    [
        ("start", "open", "in_progress"),
        ("stop", "in_progress", "open"),
        ("decline", "open", "not_planned"),
        ("decline", "in_progress", "not_planned"),
        ("reopen", "not_planned", "open"),
        ("confirm_fix", "open", "fix_available"),
        ("confirm_fix", "in_progress", "fix_available"),
    ],
)
def test_problem_transitions(action: str, state: str, expected: str) -> None:
    assert check_problem_transition(action=action, from_state=state) == expected


@pytest.mark.parametrize("check", [check_report_transition, check_problem_transition])
def test_invalid_transition_has_stable_reason_and_context(check: object) -> None:
    with pytest.raises(InvalidTransition) as error:
        check(action="start", from_state="closed")  # type: ignore[operator]
    assert error.value.reason == "invalid_transition"
    assert error.value.from_state == "closed"


@pytest.mark.parametrize(
    ("rules", "states", "check"),
    [
        (REPORT_TRANSITIONS, ("new", "linked", "dismissed"), check_report_transition),
        (
            PROBLEM_TRANSITIONS,
            ("open", "in_progress", "fix_available", "not_planned"),
            check_problem_transition,
        ),
    ],
)
def test_each_action_state_pair_matches_its_transition_table(
    rules: dict[str, tuple[frozenset[str], str]],
    states: tuple[str, ...],
    check: Callable[..., str],
) -> None:
    for action, (allowed_from, expected_to) in rules.items():
        for state in states:
            if state in allowed_from:
                assert check(action=action, from_state=state) == expected_to
            else:
                with pytest.raises(InvalidTransition) as error:
                    check(action=action, from_state=state)
                assert error.value.action == action
                assert error.value.from_state == state
