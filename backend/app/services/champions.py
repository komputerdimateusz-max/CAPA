from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.models.action import Action
from app.models.analysis import Analysis
from app.models.champion import Champion
from app.models.project import Project


ACTION_STATUS_CLOSED = {"closed"}


@dataclass(frozen=True)
class ScoreEvent:
    rule_code: str
    points: int
    details: str


@dataclass(frozen=True)
class ActionScore:
    action: Action
    champion_label: str
    events: tuple[ScoreEvent, ...]
    total_points: int
    on_time: bool | None


@dataclass(frozen=True)
class ChampionScoreSummary:
    champion_id: int | None
    champion_label: str
    total_score: int
    created_points: int
    closed_points: int
    on_time_bonus: int
    late_penalty: int
    aging_penalty: int
    actions_total: int
    actions_closed: int
    actions_late: int


@dataclass(frozen=True)
class ChampionSyncStats:
    actions_updated: int
    analyses_updated: int
    projects_updated: int


def sync_actions_champions_with_settings(db: Session) -> ChampionSyncStats:
    orphan_action_where = (
        Action.champion_id.is_not(None)
        & ~exists(select(1).where(Champion.id == Action.champion_id))
    )
    orphan_project_where = (
        Project.process_engineer_id.is_not(None)
        & ~exists(select(1).where(Champion.id == Project.process_engineer_id))
    )

    orphan_action_ids = list(db.scalars(select(Action.id).where(orphan_action_where)))
    orphan_project_ids = list(db.scalars(select(Project.id).where(orphan_project_where)))

    if orphan_action_ids:
        db.execute(update(Action).where(orphan_action_where).values(champion_id=None))
    if orphan_project_ids:
        db.execute(update(Project).where(orphan_project_where).values(process_engineer_id=None))

    analyses_updated = 0
    if hasattr(Analysis, "champion_id"):
        orphan_analysis_where = (
            Analysis.champion_id.is_not(None)
            & ~exists(select(1).where(Champion.id == Analysis.champion_id))
        )
        orphan_analysis_ids = list(db.scalars(select(Analysis.id).where(orphan_analysis_where)))
        if orphan_analysis_ids:
            db.execute(update(Analysis).where(orphan_analysis_where).values(champion_id=None))
            analyses_updated = len(orphan_analysis_ids)

    db.commit()
    return ChampionSyncStats(
        actions_updated=len(orphan_action_ids),
        analyses_updated=analyses_updated,
        projects_updated=len(orphan_project_ids),
    )


def _normalize_status(status: str | None) -> str:
    return (status or "").strip().lower()


def _compute_late_days(
    status: str,
    due_date: date | None,
    closed_at: date | None,
    today: date,
) -> int:
    if not due_date:
        return 0
    is_closed = status in ACTION_STATUS_CLOSED
    if is_closed and closed_at and closed_at > due_date:
        return (closed_at - due_date).days
    if not is_closed and today > due_date:
        return (today - due_date).days
    return 0


def _champion_label(action: Action) -> str:
    if action.champion:
        return action.champion.full_name
    return "Unassigned"


def score_actions(actions: list[Action], today: date | None = None) -> list[ActionScore]:
    today = today or date.today()
    scored: list[ActionScore] = []

    for action in actions:
        status = _normalize_status(action.status)
        events: list[ScoreEvent] = []
        champion_label = _champion_label(action)
        closed_date = action.closed_at.date() if action.closed_at else None

        if action.created_at:
            events.append(ScoreEvent("ACT_CREATE", 1, f"created_at={action.created_at.date()}"))

        is_closed = status in ACTION_STATUS_CLOSED
        if is_closed:
            events.append(ScoreEvent("ACT_CLOSE_BASE", 3, f"status={status}"))

        on_time = None
        if action.closed_at and action.due_date:
            on_time = closed_date <= action.due_date
            if on_time:
                events.append(
                    ScoreEvent(
                        "ACT_ON_TIME_BONUS",
                        2,
                        f"closed_at={closed_date}, due_date={action.due_date}",
                    )
                )
            else:
                events.append(
                    ScoreEvent(
                        "ACT_LATE_PENALTY",
                        -2,
                        f"closed_at={closed_date}, due_date={action.due_date}",
                    )
                )

        late_days = _compute_late_days(status, action.due_date, closed_date, today)
        if late_days > 14:
            events.append(ScoreEvent("PEN_ACT_LATE_14D", -1, f"late_days={late_days}"))
        if late_days > 30:
            events.append(ScoreEvent("PEN_ACT_LATE_30D", -3, f"late_days={late_days}"))

        total_points = sum(event.points for event in events)
        scored.append(
            ActionScore(
                action=action,
                champion_label=champion_label,
                events=tuple(events),
                total_points=total_points,
                on_time=on_time,
            )
        )

    return scored


def _bucket_champion(
    score: ActionScore,
    *,
    valid_champion_ids: set[int] | None,
) -> tuple[int | None, str]:
    champion_id = score.action.champion_id
    if champion_id is None:
        return None, "Unassigned"
    if valid_champion_ids is not None and champion_id not in valid_champion_ids:
        return None, "Unassigned"
    if score.action.champion is None:
        return None, "Unassigned"
    return champion_id, score.action.champion.full_name


def summarize_champions(
    scores: list[ActionScore],
    *,
    include_unassigned: bool = True,
    valid_champion_ids: Iterable[int] | None = None,
) -> list[ChampionScoreSummary]:
    valid_ids = set(valid_champion_ids) if valid_champion_ids is not None else None
    summaries: dict[int | None, dict[str, int]] = {}
    champion_labels: dict[int | None, str] = {}

    for score in scores:
        champion_id, champion_label = _bucket_champion(score, valid_champion_ids=valid_ids)
        if champion_id is None and not include_unassigned:
            continue
        summaries.setdefault(
            champion_id,
            {
                "total_score": 0,
                "created_points": 0,
                "closed_points": 0,
                "on_time_bonus": 0,
                "late_penalty": 0,
                "aging_penalty": 0,
                "actions_total": 0,
                "actions_closed": 0,
                "actions_late": 0,
            },
        )
        champion_labels[champion_id] = champion_label

        bucket = summaries[champion_id]
        bucket["total_score"] += score.total_points
        bucket["actions_total"] += 1
        if _normalize_status(score.action.status) in ACTION_STATUS_CLOSED:
            bucket["actions_closed"] += 1
        if score.on_time is False:
            bucket["actions_late"] += 1

        for event in score.events:
            if event.rule_code == "ACT_CREATE":
                bucket["created_points"] += event.points
            elif event.rule_code == "ACT_CLOSE_BASE":
                bucket["closed_points"] += event.points
            elif event.rule_code == "ACT_ON_TIME_BONUS":
                bucket["on_time_bonus"] += event.points
            elif event.rule_code == "ACT_LATE_PENALTY":
                bucket["late_penalty"] += event.points
            elif event.rule_code.startswith("PEN_ACT_LATE"):
                bucket["aging_penalty"] += event.points

    results: list[ChampionScoreSummary] = []
    for champion_id, bucket in summaries.items():
        results.append(
            ChampionScoreSummary(
                champion_id=champion_id,
                champion_label=champion_labels.get(champion_id, "Unassigned"),
                total_score=bucket["total_score"],
                created_points=bucket["created_points"],
                closed_points=bucket["closed_points"],
                on_time_bonus=bucket["on_time_bonus"],
                late_penalty=bucket["late_penalty"],
                aging_penalty=bucket["aging_penalty"],
                actions_total=bucket["actions_total"],
                actions_closed=bucket["actions_closed"],
                actions_late=bucket["actions_late"],
            )
        )

    results.sort(
        key=lambda item: (
            item.champion_id is None,
            -item.total_score,
            -item.actions_closed,
            item.champion_label.lower(),
        )
    )
    return results
