"""PostgreSQL candidate retrieval for one report.

Same method as the measured baseline in scripts/eval_baseline.py: english config, title (A),
summary (B), and linked report text (C) weights, OR-ed report words, ts_rank_cd, id tie-break.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db import connection
from django.db.models import F, Window
from django.db.models.functions import RowNumber

from feedback.models import Problem, Report
from matching.contract import MAX_CANDIDATES, Candidate

# Problems a new report can still belong to.
ELIGIBLE_PROBLEM_STATES = (Problem.State.OPEN, Problem.State.IN_PROGRESS)

# Report words are OR-ed, because plainto_tsquery ANDs every word and a long report
# would match nothing. The workspace and state filters run before ranking.
RETRIEVE = """
WITH query AS (
  SELECT replace(plainto_tsquery('english', %(text)s)::text, ' & ', ' | ')::tsquery AS q
), document AS (
  SELECT
    problem.id,
    setweight(to_tsvector('english', problem.title), 'A')
    || setweight(to_tsvector('english', problem.summary), 'B')
    || setweight(to_tsvector('english', coalesce(string_agg(
         linked.title || E'\\n' || linked.description, E'\\n'
         ORDER BY linked.created_at, linked.id
       ), '')), 'C') AS document
  FROM feedback_problem AS problem
  LEFT JOIN feedback_report AS linked
    ON linked.problem_id = problem.id AND linked.workspace_id = problem.workspace_id
  WHERE problem.workspace_id = %(workspace_id)s AND problem.state = ANY(%(states)s)
  GROUP BY problem.id
)
SELECT document.id FROM document, query
WHERE document.document @@ query.q
ORDER BY ts_rank_cd(document.document, query.q) DESC, document.id ASC
LIMIT %(limit)s
"""


@dataclass(frozen=True)
class Retrieved:
    """Request candidates and the versions that must still hold when results are saved."""

    candidates: list[Candidate]
    snapshot: list[dict[str, Any]]


def retrieve_candidate_ids(*, report: Report) -> list[UUID]:
    with connection.cursor() as cursor:
        cursor.execute(
            RETRIEVE,
            {
                "text": f"{report.title}\n{report.description}",
                "workspace_id": report.workspace_id,
                "states": list(ELIGIBLE_PROBLEM_STATES),
                "limit": MAX_CANDIDATES,
            },
        )
        return [row[0] for row in cursor.fetchall()]


def load_candidates(
    *, workspace_id: UUID, problem_ids: list[UUID], max_linked_reports: int
) -> Retrieved | None:
    """Candidates in the given order, or None if any is gone or no longer eligible.

    Each candidate carries its most recently created linked reports, up to the config's cap.
    """
    problems = {
        problem.pk: problem
        for problem in Problem.objects.filter(
            workspace_id=workspace_id, pk__in=problem_ids, state__in=ELIGIBLE_PROBLEM_STATES
        )
    }
    if len(problems) != len(problem_ids):
        return None
    linked_by_problem: dict[UUID, list[Report]] = {pk: [] for pk in problem_ids}
    linked = (
        Report.objects.filter(workspace_id=workspace_id, problem_id__in=problem_ids)
        .annotate(
            position=Window(
                RowNumber(),
                partition_by=[F("problem_id")],
                order_by=[F("created_at").desc(), F("id").asc()],
            )
        )
        .filter(position__lte=max_linked_reports)
        .order_by("problem_id", "position")
        .only("id", "problem_id", "title", "description", "version")
    )
    for report in linked:
        assert report.problem_id is not None
        linked_by_problem[report.problem_id].append(report)
    candidates: list[Candidate] = []
    snapshot: list[dict[str, Any]] = []
    for problem_id in problem_ids:
        problem = problems[problem_id]
        reports = linked_by_problem[problem_id]
        candidates.append(
            {
                "id": str(problem.pk),
                "version": problem.version,
                "title": problem.title,
                "summary": problem.summary,
                "linked_reports": [
                    {"id": str(item.pk), "title": item.title, "description": item.description}
                    for item in reports
                ],
            }
        )
        snapshot.append(
            {
                "id": str(problem.pk),
                "version": problem.version,
                "linked_reports": [
                    {"id": str(item.pk), "version": item.version} for item in reports
                ],
            }
        )
    return Retrieved(candidates=candidates, snapshot=snapshot)
