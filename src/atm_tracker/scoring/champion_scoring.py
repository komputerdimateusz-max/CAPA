from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ActionColumns:
    action_id: str | None
    champion: str | None
    status: str | None
    created_at: str | None
    due_date: str | None
    closed_at: str | None
    analysis_id: str | None


@dataclass(frozen=True)
class AnalysisColumns:
    analysis_id: str | None
    analysis_type: str | None
    champion: str | None
    status: str | None
    created_at: str | None
    closed_at: str | None


ACTION_STATUS_CLOSED = {"closed", "done"}
ANALYSIS_STATUS_CLOSED = {"closed"}

ANALYSIS_SLA_DAYS = {
    "5WHY": 14,
    "A3": 30,
    "8D": 45,
}

SCORE_LOG_COLUMNS = [
    "champion",
    "item_type",
    "item_id",
    "rule_code",
    "points",
    "as_of_date",
    "details",
]


def _normalize_column_name(value: str) -> str:
    return "".join(value.lower().replace(" ", "").replace("_", "").split())


def _find_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    normalized = {_normalize_column_name(col): col for col in columns}
    for candidate in candidates:
        key = _normalize_column_name(candidate)
        if key in normalized:
            return normalized[key]
    return None


def _coerce_date_series(series: pd.Series) -> pd.Series:
    coerced = pd.to_datetime(series, errors="coerce").dt.date
    return coerced.apply(lambda value: value if pd.notna(value) else None)


def _normalize_status(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower()


def _prepare_actions(actions_df: pd.DataFrame) -> tuple[pd.DataFrame, ActionColumns]:
    df = actions_df.copy()
    columns = ActionColumns(
        action_id=_find_column(df.columns, ["action_id", "id", "actionid"]),
        champion=_find_column(df.columns, ["champion", "owner", "responsible"]),
        status=_find_column(df.columns, ["status", "state"]),
        created_at=_find_column(df.columns, ["created_at", "created", "created_date", "date"]),
        due_date=_find_column(df.columns, ["due_date", "due", "target_date", "targetdate"]),
        closed_at=_find_column(df.columns, ["closed_at", "closed", "closed_date", "closedon"]),
        analysis_id=_find_column(df.columns, ["analysis_id", "analysis", "analysisid"]),
    )

    for col in [columns.created_at, columns.due_date, columns.closed_at]:
        if col and col in df.columns:
            df[col] = _coerce_date_series(df[col])

    action_id_values: pd.Series
    if columns.action_id and columns.action_id in df.columns:
        action_id_values = df[columns.action_id].astype(str)
    else:
        action_id_values = pd.Series([f"AUTO-{idx + 1:05d}" for idx in range(len(df))], index=df.index)
        columns = ActionColumns(
            action_id="action_id",
            champion=columns.champion,
            status=columns.status,
            created_at=columns.created_at,
            due_date=columns.due_date,
            closed_at=columns.closed_at,
            analysis_id=columns.analysis_id,
        )
        df[columns.action_id] = action_id_values

    if columns.champion and columns.champion in df.columns:
        df[columns.champion] = df[columns.champion].fillna("").astype(str)
    else:
        df["champion"] = ""
        columns = ActionColumns(
            action_id=columns.action_id,
            champion="champion",
            status=columns.status,
            created_at=columns.created_at,
            due_date=columns.due_date,
            closed_at=columns.closed_at,
            analysis_id=columns.analysis_id,
        )

    return df, columns


def _prepare_analyses(analyses_df: pd.DataFrame) -> tuple[pd.DataFrame, AnalysisColumns]:
    df = analyses_df.copy()
    columns = AnalysisColumns(
        analysis_id=_find_column(df.columns, ["analysis_id", "analysisid", "id"]),
        analysis_type=_find_column(df.columns, ["type", "analysis_type"]),
        champion=_find_column(df.columns, ["champion", "owner", "responsible"]),
        status=_find_column(df.columns, ["status", "state"]),
        created_at=_find_column(df.columns, ["created_at", "created", "created_date", "date"]),
        closed_at=_find_column(df.columns, ["closed_at", "closed", "closed_date"]),
    )

    for col in [columns.created_at, columns.closed_at]:
        if col and col in df.columns:
            df[col] = _coerce_date_series(df[col])

    if columns.champion and columns.champion in df.columns:
        df[columns.champion] = df[columns.champion].fillna("").astype(str)
    else:
        df["champion"] = ""
        columns = AnalysisColumns(
            analysis_id=columns.analysis_id,
            analysis_type=columns.analysis_type,
            champion="champion",
            status=columns.status,
            created_at=columns.created_at,
            closed_at=columns.closed_at,
        )

    return df, columns


def _add_log(
    records: list[dict[str, object]],
    champion: str,
    item_type: str,
    item_id: str,
    rule_code: str,
    points: int,
    as_of: date,
    details: str,
) -> None:
    records.append(
        {
            "champion": champion,
            "item_type": item_type,
            "item_id": item_id,
            "rule_code": rule_code,
            "points": int(points),
            "as_of_date": as_of.isoformat(),
            "details": details,
        }
    )


def compute_score_log(actions_df: pd.DataFrame, analyses_df: pd.DataFrame, today: date) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    actions_df, action_cols = _prepare_actions(actions_df)
    analyses_df, analysis_cols = _prepare_analyses(analyses_df)

    if not actions_df.empty and action_cols.action_id:
        status_values = (
            _normalize_status(actions_df[action_cols.status])
            if action_cols.status and action_cols.status in actions_df.columns
            else pd.Series(["open"] * len(actions_df), index=actions_df.index)
        )
        created_values = (
            actions_df[action_cols.created_at]
            if action_cols.created_at and action_cols.created_at in actions_df.columns
            else pd.Series([None] * len(actions_df), index=actions_df.index)
        )
        due_values = (
            actions_df[action_cols.due_date]
            if action_cols.due_date and action_cols.due_date in actions_df.columns
            else pd.Series([None] * len(actions_df), index=actions_df.index)
        )
        closed_values = (
            actions_df[action_cols.closed_at]
            if action_cols.closed_at and action_cols.closed_at in actions_df.columns
            else pd.Series([None] * len(actions_df), index=actions_df.index)
        )

        for idx, row in actions_df.iterrows():
            action_id = str(row[action_cols.action_id])
            champion = str(row.get(action_cols.champion, "") or "Unassigned").strip() or "Unassigned"
            status = str(status_values.loc[idx])
            created_at = created_values.loc[idx]
            due_date = due_values.loc[idx]
            closed_at = closed_values.loc[idx]

            if created_at:
                _add_log(
                    records,
                    champion,
                    "ACTION",
                    action_id,
                    "ACT_CREATE",
                    1,
                    today,
                    f"created_at={created_at}",
                )

            is_closed = status in ACTION_STATUS_CLOSED
            if is_closed:
                _add_log(
                    records,
                    champion,
                    "ACTION",
                    action_id,
                    "ACT_CLOSE_BASE",
                    3,
                    today,
                    f"status={status}",
                )

            closed_on_time = bool(closed_at and due_date and closed_at <= due_date)
            closed_late = bool(closed_at and due_date and closed_at > due_date)

            if closed_on_time:
                _add_log(
                    records,
                    champion,
                    "ACTION",
                    action_id,
                    "ACT_ON_TIME_BONUS",
                    2,
                    today,
                    f"closed_at={closed_at}, due_date={due_date}",
                )
            if closed_late:
                _add_log(
                    records,
                    champion,
                    "ACTION",
                    action_id,
                    "ACT_LATE_PENALTY",
                    -2,
                    today,
                    f"closed_at={closed_at}, due_date={due_date}",
                )

            late_days = 0
            if due_date:
                if is_closed and closed_at and closed_at > due_date:
                    late_days = (closed_at - due_date).days
                elif not is_closed and today > due_date:
                    late_days = (today - due_date).days

            if late_days > 14:
                _add_log(
                    records,
                    champion,
                    "PENALTY",
                    f"ACTION_LATE_AGING:{action_id}",
                    "PEN_ACT_LATE_14D",
                    -1,
                    today,
                    f"late_days={late_days}",
                )
            if late_days > 30:
                _add_log(
                    records,
                    champion,
                    "PENALTY",
                    f"ACTION_LATE_AGING:{action_id}",
                    "PEN_ACT_LATE_30D",
                    -3,
                    today,
                    f"late_days={late_days}",
                )

    if not analyses_df.empty and analysis_cols.analysis_id:
        status_values = (
            _normalize_status(analyses_df[analysis_cols.status])
            if analysis_cols.status and analysis_cols.status in analyses_df.columns
            else pd.Series(["open"] * len(analyses_df), index=analyses_df.index)
        )
        created_values = (
            analyses_df[analysis_cols.created_at]
            if analysis_cols.created_at and analysis_cols.created_at in analyses_df.columns
            else pd.Series([None] * len(analyses_df), index=analyses_df.index)
        )
        closed_values = (
            analyses_df[analysis_cols.closed_at]
            if analysis_cols.closed_at and analysis_cols.closed_at in analyses_df.columns
            else pd.Series([None] * len(analyses_df), index=analyses_df.index)
        )
        type_values = (
            analyses_df[analysis_cols.analysis_type]
            if analysis_cols.analysis_type and analysis_cols.analysis_type in analyses_df.columns
            else pd.Series([""] * len(analyses_df), index=analyses_df.index)
        )

        for idx, row in analyses_df.iterrows():
            analysis_id = str(row[analysis_cols.analysis_id])
            champion = str(row.get(analysis_cols.champion, "") or "Unassigned").strip() or "Unassigned"
            status = str(status_values.loc[idx])
            analysis_type = str(type_values.loc[idx]).strip().upper()
            created_at = created_values.loc[idx]
            closed_at = closed_values.loc[idx]

            is_closed = status in ANALYSIS_STATUS_CLOSED

            if is_closed and analysis_type in ANALYSIS_SLA_DAYS:
                base_points = {"5WHY": 5, "A3": 8, "8D": 10}[analysis_type]
                _add_log(
                    records,
                    champion,
                    "ANALYSIS",
                    analysis_id,
                    f"AN_{analysis_type}_CLOSE_BASE",
                    base_points,
                    today,
                    f"status={status}",
                )

                sla_days = ANALYSIS_SLA_DAYS[analysis_type]
                # SLA-by-type (5WHY=14, A3=30, 8D=45 days) based on created_at; no due_date column required.
                closed_on_time = bool(created_at and closed_at and closed_at <= created_at + timedelta(days=sla_days))
                if closed_on_time:
                    bonus_points = {"5WHY": 2, "A3": 3, "8D": 5}[analysis_type]
                    _add_log(
                        records,
                        champion,
                        "ANALYSIS",
                        analysis_id,
                        f"AN_{analysis_type}_ON_TIME_BONUS",
                        bonus_points,
                        today,
                        f"closed_at={closed_at}, sla_days={sla_days}",
                    )

            if not is_closed and created_at:
                age_days = (today - created_at).days
                if age_days > 30:
                    periods = math.ceil((age_days - 30) / 30)
                    _add_log(
                        records,
                        champion,
                        "PENALTY",
                        f"OPEN_ANALYSIS_AGING:{analysis_id}",
                        "PEN_OPEN_ANALYSIS_30D",
                        -2 * periods,
                        today,
                        f"age_days={age_days}, periods={periods}",
                    )
                if age_days > 90:
                    periods = math.ceil((age_days - 90) / 30)
                    _add_log(
                        records,
                        champion,
                        "PENALTY",
                        f"OPEN_ANALYSIS_AGING:{analysis_id}",
                        "PEN_OPEN_ANALYSIS_90D",
                        -5 * periods,
                        today,
                        f"age_days={age_days}, periods={periods}",
                    )

    if not records:
        return pd.DataFrame(columns=SCORE_LOG_COLUMNS)

    score_log = pd.DataFrame.from_records(records)
    score_log = score_log[SCORE_LOG_COLUMNS]
    return score_log


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


def compute_ranking(
    score_log_df: pd.DataFrame,
    actions_df: pd.DataFrame,
    analyses_df: pd.DataFrame,
) -> pd.DataFrame:
    today = date.today()
    actions_df, action_cols = _prepare_actions(actions_df)
    analyses_df, analysis_cols = _prepare_analyses(analyses_df)

    champions: set[str] = set()
    if not actions_df.empty and action_cols.champion:
        champions.update(actions_df[action_cols.champion].fillna("").astype(str).tolist())
    if not analyses_df.empty and analysis_cols.champion:
        champions.update(analyses_df[analysis_cols.champion].fillna("").astype(str).tolist())
    if not score_log_df.empty and "champion" in score_log_df.columns:
        champions.update(score_log_df["champion"].fillna("").astype(str).tolist())

    champions = {champ.strip() or "Unassigned" for champ in champions}
    if not champions:
        return pd.DataFrame(
            columns=[
                "champion",
                "total_score",
                "actions_total",
                "actions_closed",
                "actions_late_count",
                "analyses_open",
                "analyses_closed",
                "closed_5why",
                "closed_a3",
                "closed_8d",
            ]
        )

    ranking = pd.DataFrame({"champion": sorted(champions)})

    if not score_log_df.empty:
        score_totals = score_log_df.groupby("champion")["points"].sum().reset_index()
        score_totals = score_totals.rename(columns={"points": "total_score"})
        ranking = ranking.merge(score_totals, on="champion", how="left")
    else:
        ranking["total_score"] = 0

    if not actions_df.empty and action_cols.champion and action_cols.status:
        actions_df["_champion"] = actions_df[action_cols.champion].fillna("").astype(str)
        status_values = _normalize_status(actions_df[action_cols.status])
        actions_df["_status_norm"] = status_values
        actions_df["_late_days"] = actions_df.apply(
            lambda row: _compute_late_days(
                row["_status_norm"],
                row[action_cols.due_date] if action_cols.due_date else None,
                row[action_cols.closed_at] if action_cols.closed_at else None,
                today,
            ),
            axis=1,
        )
        action_summary = actions_df.groupby("_champion").agg(
            actions_total=(action_cols.action_id, "count"),
            actions_closed=("_status_norm", lambda s: int((s.isin(ACTION_STATUS_CLOSED)).sum())),
            actions_late_count=("_late_days", lambda s: int((s > 0).sum())),
        )
        action_summary = action_summary.reset_index().rename(columns={"_champion": "champion"})
        ranking = ranking.merge(action_summary, on="champion", how="left")

    if not analyses_df.empty and analysis_cols.champion and analysis_cols.status:
        analyses_df["_champion"] = analyses_df[analysis_cols.champion].fillna("").astype(str)
        status_values = _normalize_status(analyses_df[analysis_cols.status])
        analyses_df["_status_norm"] = status_values
        analyses_df["_type_norm"] = (
            analyses_df[analysis_cols.analysis_type].fillna("").astype(str).str.upper()
            if analysis_cols.analysis_type
            else ""
        )
        analysis_summary = analyses_df.groupby("_champion").agg(
            analyses_open=("_status_norm", lambda s: int((~s.isin(ANALYSIS_STATUS_CLOSED)).sum())),
            analyses_closed=("_status_norm", lambda s: int((s.isin(ANALYSIS_STATUS_CLOSED)).sum())),
            closed_5why=(
                "_type_norm",
                lambda s: int(((s == "5WHY") & (analyses_df.loc[s.index, "_status_norm"].isin(ANALYSIS_STATUS_CLOSED))).sum()),
            ),
            closed_a3=(
                "_type_norm",
                lambda s: int(((s == "A3") & (analyses_df.loc[s.index, "_status_norm"].isin(ANALYSIS_STATUS_CLOSED))).sum()),
            ),
            closed_8d=(
                "_type_norm",
                lambda s: int(((s == "8D") & (analyses_df.loc[s.index, "_status_norm"].isin(ANALYSIS_STATUS_CLOSED))).sum()),
            ),
        )
        analysis_summary = analysis_summary.reset_index().rename(columns={"_champion": "champion"})
        ranking = ranking.merge(analysis_summary, on="champion", how="left")

    count_columns = [
        "total_score",
        "actions_total",
        "actions_closed",
        "actions_late_count",
        "analyses_open",
        "analyses_closed",
        "closed_5why",
        "closed_a3",
        "closed_8d",
    ]
    for col in count_columns:
        if col not in ranking.columns:
            ranking[col] = 0
        else:
            ranking[col] = ranking[col].fillna(0).astype(int)

    ranking = ranking.sort_values(by=["total_score", "actions_closed"], ascending=[False, False])
    desired_cols = [
        "champion",
        "total_score",
        "actions_total",
        "actions_closed",
        "actions_late_count",
        "analyses_open",
        "analyses_closed",
        "closed_5why",
        "closed_a3",
        "closed_8d",
    ]
    remaining_cols = [col for col in ranking.columns if col not in desired_cols]
    ranking = ranking[desired_cols + remaining_cols]
    return ranking
