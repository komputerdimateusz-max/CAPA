from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.models.action import Action


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


def summarize_champions(scores: list[ActionScore], *, include_unassigned: bool = True) -> list[ChampionScoreSummary]:
    summaries: dict[tuple[int | None, str], dict[str, int]] = {}
    action_refs: dict[tuple[int | None, str], list[ActionScore]] = {}

    for score in scores:
        champion_id = score.action.champion_id
        if champion_id is None and not include_unassigned:
            continue
        key = (champion_id, score.champion_label)
        summaries.setdefault(
            key,
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
        action_refs.setdefault(key, []).append(score)

        bucket = summaries[key]
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
    for (champion_id, label), bucket in summaries.items():
        results.append(
            ChampionScoreSummary(
                champion_id=champion_id,
                champion_label=label,
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
