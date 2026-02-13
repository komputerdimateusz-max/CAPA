from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.champion import Champion
from app.models.moulding import MouldingMachine, MouldingTool
from app.models.project import Project
from app.repositories import moulding as moulding_repo
from app.schemas.moulding import (
    MouldingMachineCreate,
    MouldingMachineUpdate,
    MouldingToolCreate,
    MouldingToolUpdate,
)


def _normalize_name(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalize_required(value: str, label: str) -> str:
    cleaned = _normalize_name(value)
    if not cleaned:
        raise ValueError(f"Champion {label} is required.")
    return cleaned


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_email(value: str | None) -> str | None:
    cleaned = _normalize_optional(value)
    if not cleaned:
        return None
    if "@" not in cleaned:
        raise ValueError("Champion email must contain @.")
    local, _, domain = cleaned.partition("@")
    if not local or "." not in domain:
        raise ValueError("Champion email must be in a valid format.")
    return cleaned


def _normalize_date(value: date | None) -> date | None:
    return value


def _ensure_unique_full_name(
    db: Session,
    first_name: str,
    last_name: str,
    exclude_id: int | None = None,
) -> None:
    stmt = select(Champion).where(
        func.lower(Champion.first_name) == first_name.lower(),
        func.lower(Champion.last_name) == last_name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(Champion.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Champion already exists.")


def _ensure_unique_email(db: Session, email: str | None, exclude_id: int | None = None) -> None:
    if not email:
        return
    stmt = select(Champion).where(func.lower(Champion.email) == email.lower())
    if exclude_id is not None:
        stmt = stmt.where(Champion.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Champion email already exists.")



ALLOWED_PROJECT_STATUSES = ("Serial production", "Spare Parts")


def _normalize_project_status(value: str | None) -> str:
    cleaned = _normalize_optional(value)
    if cleaned is None:
        raise ValueError("Project status is required.")
    if cleaned not in ALLOWED_PROJECT_STATUSES:
        raise ValueError(f"Project status must be one of: {', '.join(ALLOWED_PROJECT_STATUSES)}.")
    return cleaned


def _normalize_project_max_volume(value: int | None) -> int:
    if value is None:
        raise ValueError("Max Volume [parts/year] is required.")
    if value < 0:
        raise ValueError("Max Volume [parts/year] must be greater than or equal to 0.")
    return value


def _normalize_project_flex(value: float | None) -> float:
    if value is None:
        raise ValueError("Flex [%] is required.")
    if value < 0 or value > 100:
        raise ValueError("Flex [%] must be between 0 and 100.")
    return value


def _normalize_process_engineer_id(db: Session, value: int | None) -> int:
    if value is None:
        raise ValueError("Process Engineer is required.")
    champion = db.get(Champion, value)
    if champion is None:
        raise ValueError("Selected Process Engineer does not exist.")
    return value

def create_champion(
    db: Session,
    first_name: str,
    last_name: str,
    email: str | None,
    position: str | None,
    birth_date: date | None,
) -> Champion:
    cleaned_first = _normalize_required(first_name, "first name")
    cleaned_last = _normalize_required(last_name, "last name")
    cleaned_email = _normalize_email(email)
    cleaned_position = _normalize_optional(position)
    _ensure_unique_full_name(db, cleaned_first, cleaned_last)
    _ensure_unique_email(db, cleaned_email)
    champion = Champion(
        first_name=cleaned_first,
        last_name=cleaned_last,
        email=cleaned_email,
        position=cleaned_position,
        birth_date=_normalize_date(birth_date),
    )
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def update_champion(
    db: Session,
    champion_id: int,
    first_name: str,
    last_name: str,
    email: str | None,
    position: str | None,
    birth_date: date | None,
) -> Champion:
    cleaned_first = _normalize_required(first_name, "first name")
    cleaned_last = _normalize_required(last_name, "last name")
    cleaned_email = _normalize_email(email)
    cleaned_position = _normalize_optional(position)
    champion = db.get(Champion, champion_id)
    if not champion:
        raise ValueError("Champion not found.")
    _ensure_unique_full_name(db, cleaned_first, cleaned_last, exclude_id=champion_id)
    _ensure_unique_email(db, cleaned_email, exclude_id=champion_id)
    champion.first_name = cleaned_first
    champion.last_name = cleaned_last
    champion.email = cleaned_email
    champion.position = cleaned_position
    champion.birth_date = _normalize_date(birth_date)
    db.add(champion)
    db.commit()
    db.refresh(champion)
    return champion


def create_project(
    db: Session,
    name: str,
    status: str | None,
    max_volume: int | None,
    flex_percent: float | None,
    process_engineer_id: int | None,
    due_date: date | None,
) -> Project:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Project name is required.")
    existing = db.scalar(select(Project).where(func.lower(Project.name) == cleaned.lower()))
    if existing:
        raise ValueError("Project already exists.")
    project = Project(
        name=cleaned,
        status=_normalize_project_status(status),
        max_volume=_normalize_project_max_volume(max_volume),
        flex_percent=_normalize_project_flex(flex_percent),
        process_engineer_id=_normalize_process_engineer_id(db, process_engineer_id),
        due_date=_normalize_date(due_date),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project_id: int,
    name: str,
    status: str | None,
    max_volume: int | None,
    flex_percent: float | None,
    process_engineer_id: int | None,
    due_date: date | None,
) -> Project:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Project name is required.")
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    existing = db.scalar(
        select(Project)
        .where(func.lower(Project.name) == cleaned.lower())
        .where(Project.id != project_id)
    )
    if existing:
        raise ValueError("Project already exists.")
    project.name = cleaned
    project.status = _normalize_project_status(status)
    project.max_volume = _normalize_project_max_volume(max_volume)
    project.flex_percent = _normalize_project_flex(flex_percent)
    project.process_engineer_id = _normalize_process_engineer_id(db, process_engineer_id)
    project.due_date = _normalize_date(due_date)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project



def _normalize_required_text(value: str, label: str) -> str:
    cleaned = " ".join(value.split()).strip()
    if not cleaned:
        raise ValueError(f"{label} is required.")
    return cleaned


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_non_negative_ct(value: float) -> float:
    if value < 0:
        raise ValueError("CT must be greater than or equal to 0.")
    return value


def _normalize_tonnage(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError("Tonnage must be greater than or equal to 0.")
    return value


def _normalize_tool_ids(tool_ids: list[int] | None) -> list[int]:
    normalized = tool_ids or []
    if len(normalized) != len(set(normalized)):
        raise ValueError("Tools assigned cannot contain duplicates.")
    return normalized


def _resolve_tools(db: Session, tool_ids: list[int]) -> list[MouldingTool]:
    if not tool_ids:
        return []
    stmt = select(MouldingTool).where(MouldingTool.id.in_(tool_ids))
    tools = list(db.scalars(stmt).all())
    found_ids = {tool.id for tool in tools}
    missing_ids = [tool_id for tool_id in tool_ids if tool_id not in found_ids]
    if missing_ids:
        raise ValueError("Selected moulding tools do not exist.")
    tools_by_id = {tool.id: tool for tool in tools}
    return [tools_by_id[tool_id] for tool_id in tool_ids]


def _ensure_unique_tool_pn(db: Session, tool_pn: str, exclude_id: int | None = None) -> None:
    stmt = select(MouldingTool).where(func.lower(MouldingTool.tool_pn) == tool_pn.lower())
    if exclude_id is not None:
        stmt = stmt.where(MouldingTool.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Tool P/N already exists.")


def _ensure_unique_machine_number(db: Session, machine_number: str, exclude_id: int | None = None) -> None:
    stmt = select(MouldingMachine).where(
        func.lower(MouldingMachine.machine_number) == machine_number.lower()
    )
    if exclude_id is not None:
        stmt = stmt.where(MouldingMachine.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Machine number already exists.")


def list_moulding_tools(db: Session) -> list[MouldingTool]:
    return moulding_repo.list_moulding_tools(db)


def create_moulding_tool(db: Session, data: MouldingToolCreate) -> MouldingTool:
    tool_pn = _normalize_required_text(data.tool_pn, "Tool P/N")
    _ensure_unique_tool_pn(db, tool_pn)
    return moulding_repo.create_moulding_tool(
        db,
        tool_pn=tool_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )


def update_moulding_tool(db: Session, tool_id: int, data: MouldingToolUpdate) -> MouldingTool:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    tool_pn = _normalize_required_text(data.tool_pn, "Tool P/N")
    _ensure_unique_tool_pn(db, tool_pn, exclude_id=tool_id)
    return moulding_repo.update_moulding_tool(
        db,
        tool=tool,
        tool_pn=tool_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )


def delete_moulding_tool(db: Session, tool_id: int) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    moulding_repo.delete_moulding_tool(db, tool=tool)


def list_moulding_machines(db: Session) -> list[MouldingMachine]:
    return moulding_repo.list_moulding_machines(db)


def create_moulding_machine(db: Session, data: MouldingMachineCreate) -> MouldingMachine:
    machine_number = _normalize_required_text(data.machine_number, "Machine number")
    _ensure_unique_machine_number(db, machine_number)
    tool_ids = _normalize_tool_ids(data.tool_ids)
    tools = _resolve_tools(db, tool_ids)
    return moulding_repo.create_moulding_machine(
        db,
        machine_number=machine_number,
        tonnage=_normalize_tonnage(data.tonnage),
        tools=tools,
    )


def update_moulding_machine(db: Session, machine_id: int, data: MouldingMachineUpdate) -> MouldingMachine:
    machine = moulding_repo.get_moulding_machine(db, machine_id)
    if machine is None:
        raise ValueError("Moulding machine not found.")
    machine_number = _normalize_required_text(data.machine_number, "Machine number")
    _ensure_unique_machine_number(db, machine_number, exclude_id=machine_id)
    tool_ids = _normalize_tool_ids(data.tool_ids)
    tools = _resolve_tools(db, tool_ids)
    return moulding_repo.update_moulding_machine(
        db,
        machine=machine,
        machine_number=machine_number,
        tonnage=_normalize_tonnage(data.tonnage),
        tools=tools,
    )


def delete_moulding_machine(db: Session, machine_id: int) -> None:
    machine = moulding_repo.get_moulding_machine(db, machine_id)
    if machine is None:
        raise ValueError("Moulding machine not found.")
    moulding_repo.delete_moulding_machine(db, machine=machine)
