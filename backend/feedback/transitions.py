"""Framework-free report and problem transition rules."""

from feedback.errors import InvalidTransition

REPORT_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "link": (frozenset({"new", "linked"}), "linked"),
    "unlink": (frozenset({"linked"}), "new"),
    "dismiss": (frozenset({"new"}), "dismissed"),
    "restore": (frozenset({"dismissed"}), "new"),
}

PROBLEM_TRANSITIONS: dict[str, tuple[frozenset[str], str]] = {
    "start": (frozenset({"open"}), "in_progress"),
    "stop": (frozenset({"in_progress"}), "open"),
    "decline": (frozenset({"open", "in_progress"}), "not_planned"),
    "reopen": (frozenset({"not_planned"}), "open"),
}

FIX_CONFIRMATION_SOURCES = frozenset({"open", "in_progress"})


def check_report_transition(*, action: str, from_state: str) -> str:
    return _check(REPORT_TRANSITIONS, action=action, from_state=from_state)


def check_problem_transition(*, action: str, from_state: str) -> str:
    return _check(PROBLEM_TRANSITIONS, action=action, from_state=from_state)


def check_fix_confirmation_transition(*, from_state: str) -> str:
    if from_state not in FIX_CONFIRMATION_SOURCES:
        raise InvalidTransition(action="confirm_fix", from_state=from_state)
    return "fix_available"


def _check(rules: dict[str, tuple[frozenset[str], str]], *, action: str, from_state: str) -> str:
    rule = rules.get(action)
    if rule is None or from_state not in rule[0]:
        raise InvalidTransition(action=action, from_state=from_state)
    return rule[1]
