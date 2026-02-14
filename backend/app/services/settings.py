from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assembly_line import AssemblyLine, AssemblyLineReference
from app.models.champion import Champion
from app.models.labour_cost import LabourCost
from app.models.material import Material
from app.models.metalization import MetalizationChamber, MetalizationMask
from app.models.moulding import MouldingMachine, MouldingTool
from app.models.project import Project
from app.repositories import assembly_lines as assembly_lines_repo
from app.repositories import labour_costs as labour_costs_repo
from app.repositories import materials as materials_repo
from app.repositories import metalization as metalization_repo
from app.repositories import moulding as moulding_repo
from app.schemas.assembly_line import (
    AssemblyLineCreate,
    AssemblyLineReferenceCreate,
    AssemblyLineReferenceUpdate,
    AssemblyLineUpdate,
)
from app.schemas.material import MaterialCreate, MaterialUpdate
from app.schemas.metalization import (
    MetalizationChamberCreate,
    MetalizationChamberUpdate,
    MetalizationMaskCreate,
    MetalizationMaskUpdate,
)
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


def _normalize_process_engineer_id(db: Session, value: int | None) -> int | None:
    if value is None:
        return None
    champion = db.get(Champion, value)
    if champion is None:
        raise ValueError("Selected Process Engineer does not exist.")
    if not champion.is_active:
        raise ValueError("Selected Process Engineer is inactive.")
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


def delete_champion(db: Session, champion_id: int) -> None:
    champion = db.get(Champion, champion_id)
    if not champion:
        raise ValueError("Champion not found.")
    db.delete(champion)
    db.commit()


def _normalize_project_assignment_ids(ids: list[int] | None, label: str) -> list[int]:
    normalized = ids or []
    deduplicated = list(dict.fromkeys(normalized))
    if any(value <= 0 for value in deduplicated):
        raise ValueError(f"{label} must contain positive IDs.")
    return deduplicated


def _resolve_project_moulding_tools(db: Session, tool_ids: list[int]) -> list[MouldingTool]:
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


def _resolve_project_assembly_lines(db: Session, line_ids: list[int]) -> list[AssemblyLine]:
    if not line_ids:
        return []
    stmt = select(AssemblyLine).where(AssemblyLine.id.in_(line_ids))
    lines = list(db.scalars(stmt).all())
    found_ids = {line.id for line in lines}
    missing_ids = [line_id for line_id in line_ids if line_id not in found_ids]
    if missing_ids:
        raise ValueError("Selected assembly lines do not exist.")
    lines_by_id = {line.id: line for line in lines}
    return [lines_by_id[line_id] for line_id in line_ids]


def _resolve_project_metalization_masks(db: Session, mask_ids: list[int]) -> list[MetalizationMask]:
    if not mask_ids:
        return []
    stmt = select(MetalizationMask).where(MetalizationMask.id.in_(mask_ids))
    masks = list(db.scalars(stmt).all())
    found_ids = {mask.id for mask in masks}
    missing_ids = [mask_id for mask_id in mask_ids if mask_id not in found_ids]
    if missing_ids:
        raise ValueError("Selected metalization masks do not exist.")
    masks_by_id = {mask.id: mask for mask in masks}
    return [masks_by_id[mask_id] for mask_id in mask_ids]


def create_project(
    db: Session,
    name: str,
    status: str | None,
    max_volume: int | None,
    flex_percent: float | None,
    process_engineer_id: int | None,
    due_date: date | None,
    moulding_tool_ids: list[int] | None = None,
    assembly_line_ids: list[int] | None = None,
    metalization_mask_ids: list[int] | None = None,
) -> Project:
    cleaned = _normalize_name(name)
    if not cleaned:
        raise ValueError("Project name is required.")
    existing = db.scalar(select(Project).where(func.lower(Project.name) == cleaned.lower()))
    if existing:
        raise ValueError("Project already exists.")
    tool_ids = _normalize_project_assignment_ids(moulding_tool_ids, "Moulding tools")
    line_ids = _normalize_project_assignment_ids(assembly_line_ids, "Assembly lines")
    tools = _resolve_project_moulding_tools(db, tool_ids)
    lines = _resolve_project_assembly_lines(db, line_ids)
    mask_ids = _normalize_project_assignment_ids(metalization_mask_ids, "Metalization masks")
    masks = _resolve_project_metalization_masks(db, mask_ids)

    project = Project(
        name=cleaned,
        status=_normalize_project_status(status),
        max_volume=_normalize_project_max_volume(max_volume),
        flex_percent=_normalize_project_flex(flex_percent),
        process_engineer_id=_normalize_process_engineer_id(db, process_engineer_id),
        due_date=_normalize_date(due_date),
    )
    project.moulding_tools = tools
    project.assembly_lines = lines
    project.metalization_masks = masks
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
    moulding_tool_ids: list[int] | None = None,
    assembly_line_ids: list[int] | None = None,
    metalization_mask_ids: list[int] | None = None,
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
    tool_ids = _normalize_project_assignment_ids(moulding_tool_ids, "Moulding tools")
    line_ids = _normalize_project_assignment_ids(assembly_line_ids, "Assembly lines")
    tools = _resolve_project_moulding_tools(db, tool_ids)
    lines = _resolve_project_assembly_lines(db, line_ids)
    mask_ids = _normalize_project_assignment_ids(metalization_mask_ids, "Metalization masks")
    masks = _resolve_project_metalization_masks(db, mask_ids)

    project.name = cleaned
    project.status = _normalize_project_status(status)
    project.max_volume = _normalize_project_max_volume(max_volume)
    project.flex_percent = _normalize_project_flex(flex_percent)
    project.process_engineer_id = _normalize_process_engineer_id(db, process_engineer_id)
    project.due_date = _normalize_date(due_date)
    project.moulding_tools = tools
    project.assembly_lines = lines
    project.metalization_masks = masks
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def add_project_moulding_tool(db: Session, project_id: int, tool_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    tool = db.get(MouldingTool, tool_id)
    if not tool:
        raise ValueError("Selected moulding tool does not exist.")
    if all(existing.id != tool.id for existing in project.moulding_tools):
        project.moulding_tools.append(tool)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def remove_project_moulding_tool(db: Session, project_id: int, tool_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    project.moulding_tools = [tool for tool in project.moulding_tools if tool.id != tool_id]
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def add_project_assembly_line(db: Session, project_id: int, line_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    line = db.get(AssemblyLine, line_id)
    if not line:
        raise ValueError("Selected assembly line does not exist.")
    if all(existing.id != line.id for existing in project.assembly_lines):
        project.assembly_lines.append(line)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def remove_project_assembly_line(db: Session, project_id: int, line_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    project.assembly_lines = [line for line in project.assembly_lines if line.id != line_id]
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def add_project_metalization_mask(db: Session, project_id: int, mask_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    mask = db.get(MetalizationMask, mask_id)
    if not mask:
        raise ValueError("Selected metalization mask does not exist.")
    if all(existing.id != mask.id for existing in project.metalization_masks):
        project.metalization_masks.append(mask)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def remove_project_metalization_mask(db: Session, project_id: int, mask_id: int) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ValueError("Project not found.")
    project.metalization_masks = [mask for mask in project.metalization_masks if mask.id != mask_id]
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


def _normalize_positive_qty_per_piece(value: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Qty / piece must be numeric.") from exc
    if parsed <= 0:
        raise ValueError("Qty / piece must be greater than 0.")
    return parsed


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


def _resolve_tool_by_pn(db: Session, tool_pn: str) -> MouldingTool | None:
    stmt = select(MouldingTool).where(func.lower(MouldingTool.tool_pn) == tool_pn.lower())
    return db.scalar(stmt)


def _resolve_material_by_part_number(db: Session, part_number: str) -> Material | None:
    stmt = select(Material).where(func.lower(Material.part_number) == part_number.lower())
    return db.scalar(stmt)


def _ensure_unique_tool_pn(db: Session, tool_pn: str, exclude_id: int | None = None) -> None:
    stmt = select(MouldingTool).where(func.lower(MouldingTool.tool_pn) == tool_pn.lower())
    if exclude_id is not None:
        stmt = stmt.where(MouldingTool.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Tool P/N already exists.")


def _ensure_unique_machine_number(
    db: Session, machine_number: str, exclude_id: int | None = None
) -> None:
    stmt = select(MouldingMachine).where(
        func.lower(MouldingMachine.machine_number) == machine_number.lower()
    )
    if exclude_id is not None:
        stmt = stmt.where(MouldingMachine.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Machine number already exists.")


def _normalize_hc_map(hc_map: dict[str, float] | None) -> dict[str, float]:
    normalized: dict[str, float] = {}
    raw = hc_map or {}
    for worker_type in LABOUR_COST_WORKER_TYPES:
        value = raw.get(worker_type, 0)
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{worker_type} HC must be numeric.") from exc
        if parsed < 0:
            raise ValueError(f"{worker_type} HC must be greater than or equal to 0.")
        normalized[worker_type] = parsed
    return normalized


def _labour_cost_map(db: Session) -> dict[str, float]:
    ensure_labour_cost_rows(db)
    return {
        row.worker_type: row.cost_pln
        for row in labour_costs_repo.list_labour_costs(db, LABOUR_COST_WORKER_TYPES)
    }


def _compute_unit_labour_cost(
    ct_seconds: float | None, hc_map: dict[str, float], labour_cost_map: dict[str, float]
) -> float:
    if ct_seconds is None or ct_seconds <= 0:
        return 0
    pieces_time_hours = ct_seconds / 3600.0
    return sum(
        pieces_time_hours * hc_map.get(worker_type, 0) * labour_cost_map.get(worker_type, 0)
        for worker_type in LABOUR_COST_WORKER_TYPES
    )


def _attach_tool_cost_fields(db: Session, tools: list[MouldingTool]) -> list[MouldingTool]:
    labour_cost_map = _labour_cost_map(db)
    material_cost_map = moulding_repo.material_cost_map_for_tools(db)
    material_out_cost_map = moulding_repo.material_out_cost_map_for_tools(db)
    for tool in tools:
        hc_map = moulding_repo.get_tool_hc_map(db, tool.id)
        tool.hc_total = sum(hc_map.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES)
        tool.unit_labour_cost = _compute_unit_labour_cost(tool.ct_seconds, hc_map, labour_cost_map)
        tool.material_cost = material_cost_map.get(tool.id, 0.0)
        tool.material_out_cost = material_out_cost_map.get(tool.id, 0.0)
    return tools


def _attach_mask_cost_fields(db: Session, masks: list[MetalizationMask]) -> list[MetalizationMask]:
    labour_cost_map = _labour_cost_map(db)
    material_cost_map = metalization_repo.material_cost_map_for_masks(db)
    material_out_cost_map = metalization_repo.material_out_cost_map_for_masks(db)
    for mask in masks:
        hc_map = metalization_repo.get_mask_hc_map(db, mask.id)
        mask.hc_total = sum(hc_map.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES)
        mask.unit_labour_cost = _compute_unit_labour_cost(mask.ct_seconds, hc_map, labour_cost_map)
        mask.material_cost = material_cost_map.get(mask.id, 0.0)
        mask.material_out_cost = material_out_cost_map.get(mask.id, 0.0)
    return masks


def _compute_reference_cost_fields(
    db: Session,
    references: list[AssemblyLineReference],
    labour_cost_map: dict[str, float] | None = None,
) -> list[AssemblyLineReference]:
    labour_cost_map = labour_cost_map or _labour_cost_map(db)
    material_in_cost_map = assembly_lines_repo.material_in_cost_map_for_references(db)
    material_out_cost_map = assembly_lines_repo.material_out_cost_map_for_references(db)
    for reference in references:
        hc_map = assembly_lines_repo.get_reference_hc_map(db, reference.id)
        reference.hc_total = sum(
            hc_map.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES
        )
        reference.unit_labour_cost = _compute_unit_labour_cost(
            reference.ct_seconds, hc_map, labour_cost_map
        )
        reference.material_cost = material_in_cost_map.get(reference.id, 0.0)
        reference.material_out_cost = material_out_cost_map.get(reference.id, 0.0)
    return references


def _attach_assembly_line_cost_fields(db: Session, lines: list[AssemblyLine]) -> list[AssemblyLine]:
    labour_cost_map = _labour_cost_map(db)
    material_in_cost_map = assembly_lines_repo.material_in_cost_map_for_lines(db)
    material_out_cost_map = assembly_lines_repo.material_out_cost_map_for_lines(db)
    for line in lines:
        references = _compute_reference_cost_fields(
            db, assembly_lines_repo.list_references_for_line(db, line.id), labour_cost_map
        )
        line.reference_count = len(references)
        if references:
            line.ct_seconds = sum(ref.ct_seconds for ref in references) / len(references)
            line.hc_total = sum(ref.hc_total for ref in references) / len(references)
            line.unit_labour_cost = sum(ref.unit_labour_cost for ref in references) / len(
                references
            )
            line.material_cost = sum(ref.material_cost for ref in references) / len(references)
            line.material_out_cost = sum(ref.material_out_cost for ref in references) / len(
                references
            )
            continue
        hc_map = assembly_lines_repo.get_line_hc_map(db, line.id)
        line.hc_total = sum(hc_map.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES)
        line.unit_labour_cost = _compute_unit_labour_cost(line.ct_seconds, hc_map, labour_cost_map)
        line.material_cost = material_in_cost_map.get(line.id, 0.0)
        line.material_out_cost = material_out_cost_map.get(line.id, 0.0)
    return lines


def get_tool_hc_map(db: Session, tool_id: int) -> dict[str, float]:
    existing = moulding_repo.get_tool_hc_map(db, tool_id)
    return {worker_type: existing.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES}


def set_tool_hc(db: Session, tool_id: int, hc_map: dict[str, float]) -> dict[str, float]:
    normalized = _normalize_hc_map(hc_map)
    moulding_repo.set_tool_hc(db, tool_id, normalized)
    db.commit()
    return normalized


def get_mask_hc_map(db: Session, mask_id: int) -> dict[str, float]:
    existing = metalization_repo.get_mask_hc_map(db, mask_id)
    return {worker_type: existing.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES}


def set_mask_hc(db: Session, mask_id: int, hc_map: dict[str, float]) -> dict[str, float]:
    normalized = _normalize_hc_map(hc_map)
    metalization_repo.set_mask_hc(db, mask_id, normalized)
    db.commit()
    return normalized


def compute_tool_unit_cost(
    db: Session, tool: MouldingTool, hc_map: dict[str, float] | None = None
) -> float:
    return _compute_unit_labour_cost(
        tool.ct_seconds, _normalize_hc_map(hc_map), _labour_cost_map(db)
    )


def compute_mask_unit_cost(
    db: Session, mask: MetalizationMask, hc_map: dict[str, float] | None = None
) -> float:
    return _compute_unit_labour_cost(
        mask.ct_seconds, _normalize_hc_map(hc_map), _labour_cost_map(db)
    )


def compute_material_cost_for_tool(db: Session, tool_id: int) -> float:
    return moulding_repo.compute_material_cost_for_tool(db, tool_id)


def compute_material_out_cost_for_tool(db: Session, tool_id: int) -> float:
    return moulding_repo.compute_material_out_cost_for_tool(db, tool_id)


def compute_material_cost_for_mask(db: Session, mask_id: int) -> float:
    return metalization_repo.compute_material_cost_for_mask(db, mask_id)


def compute_material_out_cost_for_mask(db: Session, mask_id: int) -> float:
    return metalization_repo.compute_material_out_cost_for_mask(db, mask_id)


def list_moulding_tools(db: Session) -> list[MouldingTool]:
    return _attach_tool_cost_fields(db, moulding_repo.list_moulding_tools(db))


def create_moulding_tool(db: Session, data: MouldingToolCreate) -> MouldingTool:
    tool_pn = _normalize_required_text(data.tool_pn, "Tool P/N")
    _ensure_unique_tool_pn(db, tool_pn)
    tool = moulding_repo.create_moulding_tool(
        db,
        tool_pn=tool_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )
    set_tool_hc(db, tool.id, data.hc_map)
    return moulding_repo.get_moulding_tool(db, tool.id) or tool


def update_moulding_tool(db: Session, tool_id: int, data: MouldingToolUpdate) -> MouldingTool:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    tool_pn = _normalize_required_text(data.tool_pn, "Tool P/N")
    _ensure_unique_tool_pn(db, tool_pn, exclude_id=tool_id)
    updated = moulding_repo.update_moulding_tool(
        db,
        tool=tool,
        tool_pn=tool_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )
    set_tool_hc(db, tool_id, data.hc_map)
    return moulding_repo.get_moulding_tool(db, tool_id) or updated


def delete_moulding_tool(db: Session, tool_id: int) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    moulding_repo.delete_moulding_tool(db, tool=tool)


def list_materials_for_tool(db: Session, tool_id: int):
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    rows = moulding_repo.list_materials_for_tool(db, tool_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def add_material_to_tool(
    db: Session,
    tool_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    material = (
        _resolve_material_by_part_number(db, part_number.strip())
        if part_number and part_number.strip()
        else None
    )
    if material is None and material_id is not None:
        material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Selected material does not exist.")
    moulding_repo.upsert_tool_material(
        db,
        tool_id=tool_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def update_tool_material_qty(
    db: Session, tool_id: int, material_id: int, qty_per_piece: float
) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if moulding_repo.get_tool_material(db, tool_id, material_id) is None:
        raise ValueError("Tool material assignment not found.")
    moulding_repo.upsert_tool_material(
        db,
        tool_id=tool_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def remove_material_from_tool(db: Session, tool_id: int, material_id: int) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    moulding_repo.delete_tool_material(db, tool_id=tool_id, material_id=material_id)


def list_materials_out_for_tool(db: Session, tool_id: int):
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    rows = moulding_repo.list_materials_out_for_tool(db, tool_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def add_material_out_to_tool(
    db: Session,
    tool_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    material = (
        _resolve_material_by_part_number(db, part_number.strip())
        if part_number and part_number.strip()
        else None
    )
    if material is None and material_id is not None:
        material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Selected material does not exist.")
    moulding_repo.upsert_tool_material_out(
        db,
        tool_id=tool_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material.id], _compute_tool_unit_process_cost(db, tool_id)
    )


def update_tool_material_out_qty(
    db: Session, tool_id: int, material_id: int, qty_per_piece: float
) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if moulding_repo.get_tool_material_out(db, tool_id, material_id) is None:
        raise ValueError("Tool material assignment not found.")
    moulding_repo.upsert_tool_material_out(
        db,
        tool_id=tool_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material_id], _compute_tool_unit_process_cost(db, tool_id)
    )


def remove_material_out_from_tool(db: Session, tool_id: int, material_id: int) -> None:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    moulding_repo.delete_tool_material_out(db, tool_id=tool_id, material_id=material_id)


def list_moulding_machines(db: Session) -> list[MouldingMachine]:
    return moulding_repo.list_moulding_machines(db)


def machine_by_id(db: Session, machine_id: int) -> MouldingMachine | None:
    return moulding_repo.get_moulding_machine(db, machine_id)


def list_tools_for_machine(db: Session, machine_id: int) -> list[MouldingTool]:
    return moulding_repo.list_tools_for_machine(db, machine_id)


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


def update_moulding_machine(
    db: Session, machine_id: int, data: MouldingMachineUpdate
) -> MouldingMachine:
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


def add_moulding_machine_tool(
    db: Session,
    machine_id: int,
    *,
    tool_id: int | None = None,
    tool_pn: str | None = None,
) -> MouldingMachine:
    machine = moulding_repo.get_moulding_machine(db, machine_id)
    if machine is None:
        raise ValueError("Moulding machine not found.")

    tool: MouldingTool | None = None
    if tool_pn:
        tool = _resolve_tool_by_pn(db, tool_pn.strip())
    if tool is None and tool_id is not None:
        tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Selected moulding tool does not exist.")

    if all(existing.id != tool.id for existing in machine.tools):
        machine.tools.append(tool)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def remove_moulding_machine_tool(
    db: Session,
    machine_id: int,
    *,
    tool_id: int | None = None,
    tool_pn: str | None = None,
) -> MouldingMachine:
    machine = moulding_repo.get_moulding_machine(db, machine_id)
    if machine is None:
        raise ValueError("Moulding machine not found.")

    resolved_tool_id = tool_id
    if resolved_tool_id is None and tool_pn:
        tool = _resolve_tool_by_pn(db, tool_pn.strip())
        resolved_tool_id = tool.id if tool else None

    if resolved_tool_id is not None:
        machine.tools = [tool for tool in machine.tools if tool.id != resolved_tool_id]

    db.add(machine)
    db.commit()
    db.refresh(machine)
    return machine


def _ensure_unique_assembly_line_number(
    db: Session, line_number: str, exclude_id: int | None = None
) -> None:
    stmt = select(AssemblyLine).where(func.lower(AssemblyLine.line_number) == line_number.lower())
    if exclude_id is not None:
        stmt = stmt.where(AssemblyLine.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Line number already exists.")


def list_assembly_lines(db: Session) -> list[AssemblyLine]:
    return _attach_assembly_line_cost_fields(db, assembly_lines_repo.list_assembly_lines(db))


def get_assembly_line(db: Session, assembly_line_id: int) -> AssemblyLine | None:
    return assembly_lines_repo.get_assembly_line(db, assembly_line_id)


def create_assembly_line(db: Session, data: AssemblyLineCreate) -> AssemblyLine:
    line_number = _normalize_required_text(data.line_number, "Line number")
    _ensure_unique_assembly_line_number(db, line_number)
    hc_input = data.hc_map or {}
    if not hc_input and data.hc > 0:
        hc_input = {"Operator": float(data.hc)}
    hc_map = _normalize_hc_map(hc_input)
    created = assembly_lines_repo.create_assembly_line(
        db,
        line_number=line_number,
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
        hc=int(sum(hc_map.values())),
    )
    assembly_lines_repo.set_line_hc(db, created.id, hc_map)
    db.commit()
    return assembly_lines_repo.get_assembly_line(db, created.id) or created


def update_assembly_line(
    db: Session, assembly_line_id: int, data: AssemblyLineUpdate
) -> AssemblyLine:
    assembly_line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if assembly_line is None:
        raise ValueError("Assembly line not found.")

    next_line_number = _normalize_required_text(
        data.line_number or assembly_line.line_number, "Line number"
    )
    next_ct_seconds = _normalize_non_negative_ct(
        data.ct_seconds if data.ct_seconds is not None else assembly_line.ct_seconds
    )

    _ensure_unique_assembly_line_number(db, next_line_number, exclude_id=assembly_line_id)

    existing_hc_map = get_assembly_line_hc_map(db, assembly_line_id)
    if data.hc_map is not None:
        next_hc_map = _normalize_hc_map(data.hc_map)
    elif data.hc is not None:
        next_hc_map = _normalize_hc_map({"Operator": float(data.hc)})
    else:
        next_hc_map = existing_hc_map

    updated = assembly_lines_repo.update_assembly_line(
        db,
        assembly_line=assembly_line,
        line_number=next_line_number,
        ct_seconds=next_ct_seconds,
        hc=int(sum(next_hc_map.values())),
    )
    assembly_lines_repo.set_line_hc(db, assembly_line_id, next_hc_map)
    db.commit()
    return assembly_lines_repo.get_assembly_line(db, assembly_line_id) or updated


def get_assembly_line_hc_map(db: Session, assembly_line_id: int) -> dict[str, float]:
    existing = assembly_lines_repo.get_line_hc_map(db, assembly_line_id)
    return {worker_type: existing.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES}


def set_assembly_line_hc(
    db: Session, assembly_line_id: int, hc_map: dict[str, float]
) -> dict[str, float]:
    normalized = _normalize_hc_map(hc_map)
    assembly_line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if assembly_line is None:
        raise ValueError("Assembly line not found.")
    assembly_line.hc = int(sum(normalized.values()))
    db.add(assembly_line)
    assembly_lines_repo.set_line_hc(db, assembly_line_id, normalized)
    db.commit()
    return normalized


def list_materials_in_for_assembly_line(db: Session, assembly_line_id: int):
    assembly_line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if assembly_line is None:
        raise ValueError("Assembly line not found.")
    rows = assembly_lines_repo.list_materials_in_for_line(db, assembly_line_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def list_materials_out_for_assembly_line(db: Session, assembly_line_id: int):
    assembly_line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if assembly_line is None:
        raise ValueError("Assembly line not found.")
    rows = assembly_lines_repo.list_materials_out_for_line(db, assembly_line_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def _resolve_material_for_line(db: Session, material_id: int | None, part_number: str | None):
    material = (
        _resolve_material_by_part_number(db, part_number.strip())
        if part_number and part_number.strip()
        else None
    )
    if material is None and material_id is not None:
        material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Selected material does not exist.")
    return material


def add_material_in_to_assembly_line(
    db: Session,
    assembly_line_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    material = _resolve_material_for_line(db, material_id, part_number)
    assembly_lines_repo.upsert_line_material_in(
        db,
        line_id=assembly_line_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def update_assembly_line_material_in_qty(
    db: Session, assembly_line_id: int, material_id: int, qty_per_piece: float
) -> None:
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if assembly_lines_repo.get_line_material_in(db, assembly_line_id, material_id) is None:
        raise ValueError("Assembly line material assignment not found.")
    assembly_lines_repo.upsert_line_material_in(
        db,
        line_id=assembly_line_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def remove_material_in_from_assembly_line(
    db: Session, assembly_line_id: int, material_id: int
) -> None:
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    assembly_lines_repo.delete_line_material_in(
        db, line_id=assembly_line_id, material_id=material_id
    )


def add_material_out_to_assembly_line(
    db: Session,
    assembly_line_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    material = _resolve_material_for_line(db, material_id, part_number)
    assembly_lines_repo.upsert_line_material_out(
        db,
        line_id=assembly_line_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material.id], _compute_assembly_line_unit_process_cost(db, assembly_line_id)
    )


def update_assembly_line_material_out_qty(
    db: Session, assembly_line_id: int, material_id: int, qty_per_piece: float
) -> None:
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if assembly_lines_repo.get_line_material_out(db, assembly_line_id, material_id) is None:
        raise ValueError("Assembly line material assignment not found.")
    assembly_lines_repo.upsert_line_material_out(
        db,
        line_id=assembly_line_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material_id], _compute_assembly_line_unit_process_cost(db, assembly_line_id)
    )


def remove_material_out_from_assembly_line(
    db: Session, assembly_line_id: int, material_id: int
) -> None:
    if assembly_lines_repo.get_assembly_line(db, assembly_line_id) is None:
        raise ValueError("Assembly line not found.")
    assembly_lines_repo.delete_line_material_out(
        db, line_id=assembly_line_id, material_id=material_id
    )


def delete_assembly_line(db: Session, assembly_line_id: int) -> None:
    assembly_line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if assembly_line is None:
        raise ValueError("Assembly line not found.")
    assembly_lines_repo.delete_assembly_line(db, assembly_line=assembly_line)


def _ensure_unique_reference_name(
    db: Session, line_id: int, reference_name: str, exclude_id: int | None = None
) -> None:
    existing = assembly_lines_repo.get_reference_by_name(db, line_id, reference_name)
    if existing is not None and existing.id != exclude_id:
        raise ValueError("Reference name already exists for this line.")


def _resolve_fg_material(db: Session, fg_material_id: int | None) -> int | None:
    if fg_material_id is None:
        return None
    if materials_repo.get_material(db, fg_material_id) is None:
        raise ValueError("Selected material does not exist.")
    return fg_material_id


def list_assembly_line_references(db: Session, line_id: int) -> list[AssemblyLineReference]:
    if assembly_lines_repo.get_assembly_line(db, line_id) is None:
        raise ValueError("Assembly line not found.")
    return _compute_reference_cost_fields(
        db, assembly_lines_repo.list_references_for_line(db, line_id)
    )


def get_assembly_line_reference(db: Session, reference_id: int) -> AssemblyLineReference | None:
    return assembly_lines_repo.get_reference(db, reference_id)


def get_assembly_line_reference_hc_map(db: Session, reference_id: int) -> dict[str, float]:
    existing = assembly_lines_repo.get_reference_hc_map(db, reference_id)
    return {worker_type: existing.get(worker_type, 0) for worker_type in LABOUR_COST_WORKER_TYPES}


def create_assembly_line_reference(
    db: Session, line_id: int, data: AssemblyLineReferenceCreate
) -> AssemblyLineReference:
    if assembly_lines_repo.get_assembly_line(db, line_id) is None:
        raise ValueError("Assembly line not found.")
    reference_name = _normalize_required_text(data.reference_name, "Reference name")
    _ensure_unique_reference_name(db, line_id, reference_name)
    created = assembly_lines_repo.create_reference(
        db,
        line_id=line_id,
        reference_name=reference_name,
        fg_material_id=_resolve_fg_material(db, data.fg_material_id),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )
    assembly_lines_repo.set_reference_hc(db, created.id, _normalize_hc_map(data.hc_map))
    db.commit()
    return assembly_lines_repo.get_reference(db, created.id) or created


def update_assembly_line_reference(
    db: Session, reference_id: int, data: AssemblyLineReferenceUpdate
) -> AssemblyLineReference:
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")

    reference_name = _normalize_required_text(
        data.reference_name or reference.reference_name, "Reference name"
    )
    _ensure_unique_reference_name(db, reference.line_id, reference_name, exclude_id=reference_id)

    updated = assembly_lines_repo.update_reference(
        db,
        reference=reference,
        reference_name=reference_name,
        fg_material_id=_resolve_fg_material(
            db, data.fg_material_id if data.fg_material_id is not None else reference.fg_material_id
        ),
        ct_seconds=_normalize_non_negative_ct(
            data.ct_seconds if data.ct_seconds is not None else reference.ct_seconds
        ),
    )
    if data.hc_map is not None:
        assembly_lines_repo.set_reference_hc(db, reference_id, _normalize_hc_map(data.hc_map))
        db.commit()
    return assembly_lines_repo.get_reference(db, reference_id) or updated


def delete_assembly_line_reference(db: Session, reference_id: int) -> None:
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")
    assembly_lines_repo.delete_reference(db, reference=reference)


def list_materials_in_for_reference(db: Session, reference_id: int):
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")
    rows = assembly_lines_repo.list_materials_in_for_reference(db, reference_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def list_materials_out_for_reference(db: Session, reference_id: int):
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")
    rows = assembly_lines_repo.list_materials_out_for_reference(db, reference_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def add_material_in_to_reference(
    db: Session,
    reference_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    if assembly_lines_repo.get_reference(db, reference_id) is None:
        raise ValueError("Assembly line reference not found.")
    material = _resolve_material_for_line(db, material_id, part_number)
    assembly_lines_repo.upsert_reference_material_in(
        db,
        reference_id=reference_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def update_reference_material_in_qty(
    db: Session, reference_id: int, material_id: int, qty_per_piece: float
) -> None:
    if assembly_lines_repo.get_reference(db, reference_id) is None:
        raise ValueError("Assembly line reference not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if assembly_lines_repo.get_reference_material_in(db, reference_id, material_id) is None:
        raise ValueError("Reference material assignment not found.")
    assembly_lines_repo.upsert_reference_material_in(
        db,
        reference_id=reference_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def remove_material_in_from_reference(db: Session, reference_id: int, material_id: int) -> None:
    if assembly_lines_repo.get_reference(db, reference_id) is None:
        raise ValueError("Assembly line reference not found.")
    assembly_lines_repo.delete_reference_material_in(
        db, reference_id=reference_id, material_id=material_id
    )


def add_material_out_to_reference(
    db: Session,
    reference_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")
    material = _resolve_material_for_line(db, material_id, part_number)
    assembly_lines_repo.upsert_reference_material_out(
        db,
        reference_id=reference_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material.id], _compute_assembly_reference_unit_process_cost(db, reference_id)
    )


def update_reference_material_out_qty(
    db: Session, reference_id: int, material_id: int, qty_per_piece: float
) -> None:
    if assembly_lines_repo.get_reference(db, reference_id) is None:
        raise ValueError("Assembly line reference not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if assembly_lines_repo.get_reference_material_out(db, reference_id, material_id) is None:
        raise ValueError("Reference material assignment not found.")
    assembly_lines_repo.upsert_reference_material_out(
        db,
        reference_id=reference_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material_id], _compute_assembly_reference_unit_process_cost(db, reference_id)
    )


def remove_material_out_from_reference(db: Session, reference_id: int, material_id: int) -> None:
    if assembly_lines_repo.get_reference(db, reference_id) is None:
        raise ValueError("Assembly line reference not found.")
    assembly_lines_repo.delete_reference_material_out(
        db, reference_id=reference_id, material_id=material_id
    )


def _normalize_mask_ids(mask_ids: list[int] | None) -> list[int]:
    normalized = mask_ids or []
    if len(normalized) != len(set(normalized)):
        raise ValueError("Masks assigned cannot contain duplicates.")
    return normalized


def _resolve_masks(db: Session, mask_ids: list[int]) -> list[MetalizationMask]:
    if not mask_ids:
        return []
    stmt = select(MetalizationMask).where(MetalizationMask.id.in_(mask_ids))
    masks = list(db.scalars(stmt).all())
    found_ids = {mask.id for mask in masks}
    missing_ids = [mask_id for mask_id in mask_ids if mask_id not in found_ids]
    if missing_ids:
        raise ValueError("Selected metalization masks do not exist.")
    masks_by_id = {mask.id: mask for mask in masks}
    return [masks_by_id[mask_id] for mask_id in mask_ids]


def _resolve_mask_by_pn(db: Session, mask_pn: str) -> MetalizationMask | None:
    stmt = select(MetalizationMask).where(func.lower(MetalizationMask.mask_pn) == mask_pn.lower())
    return db.scalar(stmt)


def _ensure_unique_mask_pn(db: Session, mask_pn: str, exclude_id: int | None = None) -> None:
    stmt = select(MetalizationMask).where(func.lower(MetalizationMask.mask_pn) == mask_pn.lower())
    if exclude_id is not None:
        stmt = stmt.where(MetalizationMask.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Mask P/N already exists.")


def _ensure_unique_chamber_number(
    db: Session, chamber_number: str, exclude_id: int | None = None
) -> None:
    stmt = select(MetalizationChamber).where(
        func.lower(MetalizationChamber.chamber_number) == chamber_number.lower()
    )
    if exclude_id is not None:
        stmt = stmt.where(MetalizationChamber.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Chamber number already exists.")


def list_metalization_masks(db: Session) -> list[MetalizationMask]:
    return _attach_mask_cost_fields(db, metalization_repo.list_metalization_masks(db))


def create_metalization_mask(db: Session, data: MetalizationMaskCreate) -> MetalizationMask:
    mask_pn = _normalize_required_text(data.mask_pn, "Mask P/N")
    _ensure_unique_mask_pn(db, mask_pn)
    mask = metalization_repo.create_metalization_mask(
        db,
        mask_pn=mask_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )
    set_mask_hc(db, mask.id, data.hc_map)
    return metalization_repo.get_metalization_mask(db, mask.id) or mask


def update_metalization_mask(
    db: Session, mask_id: int, data: MetalizationMaskUpdate
) -> MetalizationMask:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    mask_pn = _normalize_required_text(data.mask_pn, "Mask P/N")
    _ensure_unique_mask_pn(db, mask_pn, exclude_id=mask_id)
    updated = metalization_repo.update_metalization_mask(
        db,
        mask=mask,
        mask_pn=mask_pn,
        description=_normalize_optional_text(data.description),
        ct_seconds=_normalize_non_negative_ct(data.ct_seconds),
    )
    set_mask_hc(db, mask_id, data.hc_map)
    return metalization_repo.get_metalization_mask(db, mask_id) or updated


def delete_metalization_mask(db: Session, mask_id: int) -> None:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    metalization_repo.delete_metalization_mask(db, mask=mask)


def list_materials_for_mask(db: Session, mask_id: int):
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    rows = metalization_repo.list_materials_for_mask(db, mask_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def add_material_to_mask(
    db: Session,
    mask_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    material = (
        _resolve_material_by_part_number(db, part_number.strip())
        if part_number and part_number.strip()
        else None
    )
    if material is None and material_id is not None:
        material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Selected material does not exist.")
    metalization_repo.upsert_mask_material(
        db,
        mask_id=mask_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def update_mask_material_qty(
    db: Session, mask_id: int, material_id: int, qty_per_piece: float
) -> None:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if metalization_repo.get_mask_material(db, mask_id, material_id) is None:
        raise ValueError("Mask material assignment not found.")
    metalization_repo.upsert_mask_material(
        db,
        mask_id=mask_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )


def remove_material_from_mask(db: Session, mask_id: int, material_id: int) -> None:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    metalization_repo.delete_mask_material(db, mask_id=mask_id, material_id=material_id)


def list_materials_out_for_mask(db: Session, mask_id: int):
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    rows = metalization_repo.list_materials_out_for_mask(db, mask_id)
    return sorted(rows, key=lambda row: row.material.part_number.lower())


def add_material_out_to_mask(
    db: Session,
    mask_id: int,
    *,
    material_id: int | None = None,
    part_number: str | None = None,
    qty_per_piece: float,
):
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    material = (
        _resolve_material_by_part_number(db, part_number.strip())
        if part_number and part_number.strip()
        else None
    )
    if material is None and material_id is not None:
        material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Selected material does not exist.")
    metalization_repo.upsert_mask_material_out(
        db,
        mask_id=mask_id,
        material_id=material.id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material.id], _compute_mask_unit_process_cost(db, mask_id)
    )


def update_mask_material_out_qty(
    db: Session, mask_id: int, material_id: int, qty_per_piece: float
) -> None:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    if materials_repo.get_material(db, material_id) is None:
        raise ValueError("Selected material does not exist.")
    if metalization_repo.get_mask_material_out(db, mask_id, material_id) is None:
        raise ValueError("Mask material assignment not found.")
    metalization_repo.upsert_mask_material_out(
        db,
        mask_id=mask_id,
        material_id=material_id,
        qty_per_piece=_normalize_positive_qty_per_piece(qty_per_piece),
    )
    _update_make_material_prices_from_process_cost(
        db, [material_id], _compute_mask_unit_process_cost(db, mask_id)
    )


def remove_material_out_from_mask(db: Session, mask_id: int, material_id: int) -> None:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    metalization_repo.delete_mask_material_out(db, mask_id=mask_id, material_id=material_id)


def list_metalization_chambers(db: Session) -> list[MetalizationChamber]:
    return metalization_repo.list_metalization_chambers(db)


def list_masks_for_chamber(
    db: Session, chamber_id: int
) -> tuple[MetalizationChamber, list[MetalizationMask]]:
    chamber = metalization_repo.get_metalization_chamber(db, chamber_id)
    if chamber is None:
        raise ValueError("Metalization chamber not found.")
    sorted_masks = sorted(chamber.masks, key=lambda mask: mask.mask_pn.lower())
    return chamber, _attach_mask_cost_fields(db, sorted_masks)


def create_metalization_chamber(
    db: Session, data: MetalizationChamberCreate
) -> MetalizationChamber:
    chamber_number = _normalize_required_text(data.chamber_number, "Chamber number")
    _ensure_unique_chamber_number(db, chamber_number)
    mask_ids = _normalize_mask_ids(data.mask_ids)
    masks = _resolve_masks(db, mask_ids)
    return metalization_repo.create_metalization_chamber(
        db,
        chamber_number=chamber_number,
        masks=masks,
    )


def update_metalization_chamber(
    db: Session, chamber_id: int, data: MetalizationChamberUpdate
) -> MetalizationChamber:
    chamber = metalization_repo.get_metalization_chamber(db, chamber_id)
    if chamber is None:
        raise ValueError("Metalization chamber not found.")
    chamber_number = _normalize_required_text(data.chamber_number, "Chamber number")
    _ensure_unique_chamber_number(db, chamber_number, exclude_id=chamber_id)
    mask_ids = _normalize_mask_ids(data.mask_ids)
    masks = _resolve_masks(db, mask_ids)
    return metalization_repo.update_metalization_chamber(
        db,
        chamber=chamber,
        chamber_number=chamber_number,
        masks=masks,
    )


def delete_metalization_chamber(db: Session, chamber_id: int) -> None:
    chamber = metalization_repo.get_metalization_chamber(db, chamber_id)
    if chamber is None:
        raise ValueError("Metalization chamber not found.")
    metalization_repo.delete_metalization_chamber(db, chamber=chamber)


def add_metalization_chamber_mask(
    db: Session,
    chamber_id: int,
    *,
    mask_id: int | None = None,
    mask_pn: str | None = None,
) -> MetalizationChamber:
    chamber = metalization_repo.get_metalization_chamber(db, chamber_id)
    if chamber is None:
        raise ValueError("Metalization chamber not found.")

    mask: MetalizationMask | None = None
    if mask_pn:
        mask = _resolve_mask_by_pn(db, mask_pn.strip())
    if mask is None and mask_id is not None:
        mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Selected metalization mask does not exist.")

    if all(existing.id != mask.id for existing in chamber.masks):
        chamber.masks.append(mask)
    db.add(chamber)
    db.commit()
    db.refresh(chamber)
    return chamber


def remove_metalization_chamber_mask(
    db: Session,
    chamber_id: int,
    *,
    mask_id: int | None = None,
    mask_pn: str | None = None,
) -> MetalizationChamber:
    chamber = metalization_repo.get_metalization_chamber(db, chamber_id)
    if chamber is None:
        raise ValueError("Metalization chamber not found.")

    resolved_mask_id = mask_id
    if resolved_mask_id is None and mask_pn:
        mask = _resolve_mask_by_pn(db, mask_pn.strip())
        resolved_mask_id = mask.id if mask else None

    if resolved_mask_id is not None:
        chamber.masks = [mask for mask in chamber.masks if mask.id != resolved_mask_id]

    db.add(chamber)
    db.commit()
    db.refresh(chamber)
    return chamber


LABOUR_COST_WORKER_TYPES = (
    "Operator",
    "Logistic",
    "TeamLeader",
    "Inspector",
    "Specialist",
    "Technican",
)


def ensure_labour_cost_rows(db: Session) -> None:
    existing = {
        row.worker_type for row in labour_costs_repo.list_labour_costs(db, LABOUR_COST_WORKER_TYPES)
    }
    missing = [
        worker_type for worker_type in LABOUR_COST_WORKER_TYPES if worker_type not in existing
    ]
    for worker_type in missing:
        labour_costs_repo.create_labour_cost(db, worker_type=worker_type, cost_pln=0)


def _validate_worker_type(worker_type: str) -> str:
    cleaned = worker_type.strip()
    if cleaned not in LABOUR_COST_WORKER_TYPES:
        raise ValueError(f"Worker type must be one of: {', '.join(LABOUR_COST_WORKER_TYPES)}.")
    return cleaned


def _validate_cost_pln(cost_pln: float) -> float:
    try:
        value = float(cost_pln)
    except (TypeError, ValueError) as exc:
        raise ValueError("Cost [PLN] must be numeric.") from exc
    if value < 0:
        raise ValueError("Cost [PLN] must be greater than or equal to 0.")
    return value


def list_labour_costs(db: Session) -> list[LabourCost]:
    ensure_labour_cost_rows(db)
    return labour_costs_repo.list_labour_costs(db, LABOUR_COST_WORKER_TYPES)


def update_labour_cost(db: Session, worker_type: str, cost_pln: float) -> LabourCost:
    normalized_worker_type = _validate_worker_type(worker_type)
    normalized_cost_pln = _validate_cost_pln(cost_pln)
    labour_cost = labour_costs_repo.get_by_worker_type(db, normalized_worker_type)
    if labour_cost is None:
        labour_cost = labour_costs_repo.create_labour_cost(
            db, worker_type=normalized_worker_type, cost_pln=0
        )
    return labour_costs_repo.update_labour_cost(
        db, labour_cost=labour_cost, cost_pln=normalized_cost_pln
    )


def _ensure_unique_material_part_number(
    db: Session, part_number: str, exclude_id: int | None = None
) -> None:
    stmt = select(Material).where(func.lower(Material.part_number) == part_number.lower())
    if exclude_id is not None:
        stmt = stmt.where(Material.id != exclude_id)
    if db.scalar(stmt):
        raise ValueError("Part number already exists.")


def _normalize_non_negative_price(value: float | None) -> float | None:
    if value is None:
        return None
    if value < 0:
        raise ValueError("Price per unit must be greater than or equal to 0.")
    return float(value)


def _normalize_material_price_for_make_buy(
    *, make_buy: bool, price_per_unit: float | None
) -> float | None:
    normalized_price = _normalize_non_negative_price(price_per_unit)
    if make_buy:
        return None
    if normalized_price is None:
        raise ValueError("Price per unit is required for BUY material.")
    return normalized_price


def _update_make_material_prices_from_process_cost(
    db: Session, material_ids: list[int], unit_process_cost: float
) -> None:
    for material_id in dict.fromkeys(material_ids):
        material = materials_repo.get_material(db, material_id)
        if material is None or not material.make_buy:
            continue
        material.price_per_unit = float(unit_process_cost)
        db.add(material)
    db.commit()


def _compute_tool_unit_process_cost(db: Session, tool_id: int) -> float:
    tool = moulding_repo.get_moulding_tool(db, tool_id)
    if tool is None:
        raise ValueError("Moulding tool not found.")
    labour_cost = compute_tool_unit_cost(db, tool, moulding_repo.get_tool_hc_map(db, tool_id))
    material_income_cost = compute_material_cost_for_tool(db, tool_id)
    return float(labour_cost + material_income_cost)


def _compute_mask_unit_process_cost(db: Session, mask_id: int) -> float:
    mask = metalization_repo.get_metalization_mask(db, mask_id)
    if mask is None:
        raise ValueError("Metalization mask not found.")
    labour_cost = compute_mask_unit_cost(db, mask, metalization_repo.get_mask_hc_map(db, mask_id))
    material_income_cost = compute_material_cost_for_mask(db, mask_id)
    return float(labour_cost + material_income_cost)


def _compute_assembly_reference_unit_process_cost(db: Session, reference_id: int) -> float:
    reference = assembly_lines_repo.get_reference(db, reference_id)
    if reference is None:
        raise ValueError("Assembly line reference not found.")
    labour_cost = _compute_unit_labour_cost(
        reference.ct_seconds,
        assembly_lines_repo.get_reference_hc_map(db, reference_id),
        _labour_cost_map(db),
    )
    material_income_cost = assembly_lines_repo.material_in_cost_map_for_references(db).get(
        reference_id, 0.0
    )
    return float(labour_cost + material_income_cost)


def _compute_assembly_line_unit_process_cost(db: Session, assembly_line_id: int) -> float:
    line = assembly_lines_repo.get_assembly_line(db, assembly_line_id)
    if line is None:
        raise ValueError("Assembly line not found.")
    labour_cost = _compute_unit_labour_cost(
        line.ct_seconds,
        assembly_lines_repo.get_line_hc_map(db, assembly_line_id),
        _labour_cost_map(db),
    )
    material_income_cost = assembly_lines_repo.material_in_cost_map_for_lines(db).get(
        assembly_line_id, 0.0
    )
    return float(labour_cost + material_income_cost)


def list_materials(db: Session) -> list[Material]:
    return materials_repo.list_materials(db)


def create_material(db: Session, data: MaterialCreate) -> Material:
    part_number = _normalize_required_text(data.part_number, "Part number")
    unit = _normalize_required_text(data.unit, "Unit")
    _ensure_unique_material_part_number(db, part_number)
    return materials_repo.create_material(
        db,
        part_number=part_number,
        description=_normalize_optional_text(data.description),
        unit=unit,
        price_per_unit=_normalize_material_price_for_make_buy(
            make_buy=data.make_buy, price_per_unit=data.price_per_unit
        ),
        category=data.category,
        make_buy=data.make_buy,
    )


def update_material(db: Session, material_id: int, data: MaterialUpdate) -> Material:
    material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Material not found.")
    part_number = _normalize_required_text(data.part_number, "Part number")
    unit = _normalize_required_text(data.unit, "Unit")
    _ensure_unique_material_part_number(db, part_number, exclude_id=material_id)
    return materials_repo.update_material(
        db,
        material=material,
        part_number=part_number,
        description=_normalize_optional_text(data.description),
        unit=unit,
        price_per_unit=_normalize_material_price_for_make_buy(
            make_buy=data.make_buy, price_per_unit=data.price_per_unit
        ),
        category=data.category,
        make_buy=data.make_buy,
    )


def delete_material(db: Session, material_id: int) -> None:
    material = materials_repo.get_material(db, material_id)
    if material is None:
        raise ValueError("Material not found.")
    materials_repo.delete_material(db, material=material)
