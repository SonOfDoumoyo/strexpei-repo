from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from ...core.errors import ValidationFailed
from ...core.timeutil import utcnow
from ...schemas.requests import (
    BankIn,
    BulkStaffIn,
    GenerateIdsIn,
    PasteIdsIn,
    RoleIn,
    RoleUpdateIn,
    StaffCreateIn,
    StaffIdsIn,
    StaffUpdateIn,
)
from ...services import analytics, billing, roles
from ...services import staff as service
from ..deps import Manager, OwnedWorkgroup, SessionDep

router = APIRouter(prefix="/workgroups/{workgroup_id}", tags=["staff"])

MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def _download(content: bytes, filename: str, media_type: str) -> Response:
    return Response(content=content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                                                     "Cache-Control": "no-store"})


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "workgroup"


# ------------------------------------------------------------------ staff
@router.get("/staff")
async def list_staff(
    workgroup: OwnedWorkgroup,
    session: SessionDep,
    status_: Literal["registered", "pending", "inactive"] | None = Query(None, alias="status"),
    q: str | None = Query(None, max_length=80),
    role_id: uuid.UUID | None = None,
    attention: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    items, total = await service.list_staff(session, workgroup.id, status=status_, query=q, role_id=role_id, attention=attention,
                                            page=page, page_size=page_size)
    return {"items": [service.staff_out(m) for m in items], "total": total, "page": page, "page_size": page_size}


@router.post("/staff", status_code=status.HTTP_201_CREATED)
async def add_staff(body: StaffCreateIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    member = await service.add_manual(session, workgroup, user, body.model_dump())
    await session.commit()
    return service.staff_out(member, full_account=True)


@router.post("/staff/bulk")
async def bulk_update(body: BulkStaffIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, int]:
    data: dict[str, Any] = {}
    if body.clear_salary_override:
        data["salary_kobo"] = None
    elif body.salary_kobo is not None:
        data["salary_kobo"] = body.salary_kobo
    if "role_id" in body.model_fields_set:
        data["role_id"] = body.role_id
    if not data:
        raise ValidationFailed("Choose a salary or role to apply.")
    count = await service.bulk_update(session, workgroup, user, body.staff_ids, data)
    await session.commit()
    return {"updated": count}


@router.get("/staff/export")
async def export_staff(workgroup: OwnedWorkgroup, session: SessionDep, format: Literal["csv", "xlsx"] = "csv") -> Response:
    header, rows = await service.export_rows(session, workgroup.id, only_ids=False)
    name = f"{_slug(workgroup.name)}-staff-{utcnow():%Y%m%d}"
    if format == "xlsx":
        return _download(service.to_xlsx(header, rows, "Staff"), f"{name}.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return _download(service.to_csv(header, rows), f"{name}.csv", "text/csv; charset=utf-8")


@router.get("/staff/{staff_id}")
async def get_staff(staff_id: uuid.UUID, workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    member = await service.get_staff(session, workgroup.id, staff_id)
    data = service.staff_out(member, full_account=True)
    data["payments"] = await analytics.staff_payment_history(session, workgroup.id, member.id)
    return data


@router.patch("/staff/{staff_id}")
async def update_staff(staff_id: uuid.UUID, body: StaffUpdateIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    member = await service.get_staff(session, workgroup.id, staff_id)
    await service.update_staff(session, workgroup, member, user, body.model_dump(exclude_unset=True))
    await session.commit()
    return service.staff_out(member, full_account=True)


@router.post("/staff/{staff_id}/bank")
async def change_bank(staff_id: uuid.UUID, body: BankIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    member = await service.get_staff(session, workgroup.id, staff_id)
    await service.change_bank(session, workgroup, member, user, body.account_number, body.bank_code)
    await session.commit()
    return service.staff_out(member, full_account=True)


@router.post("/staff/{staff_id}/reset")
async def reset_staff(staff_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    member = await service.get_staff(session, workgroup.id, staff_id)
    await service.reset_registration(session, workgroup, member, user)
    await session.commit()
    return service.staff_out(member)


@router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, str]:
    member = await service.get_staff(session, workgroup.id, staff_id)
    outcome = await service.delete_staff(session, workgroup, member, user)
    await session.commit()
    return {"outcome": outcome}


# --------------------------------------------------------------- staff IDs
async def _ids_summary(session, workgroup) -> dict[str, Any]:
    in_use = await billing.seats_in_use(session, workgroup.id)
    return {"headcount": workgroup.headcount, "in_use": in_use, "remaining": max(0, workgroup.headcount - in_use)}


@router.get("/staff-ids/summary")
async def ids_summary(workgroup: OwnedWorkgroup, session: SessionDep) -> dict[str, Any]:
    return await _ids_summary(session, workgroup)


@router.post("/staff-ids/generate", status_code=status.HTTP_201_CREATED)
async def generate_ids(body: GenerateIdsIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    created = await service.generate_ids(session, workgroup, body.count, user)
    await session.commit()
    return {"created": len(created), "codes": [m.staff_code for m in created[:200]], "summary": await _ids_summary(session, workgroup)}


@router.post("/staff-ids/upload")
async def upload_ids(workgroup: OwnedWorkgroup, user: Manager, session: SessionDep, file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationFailed("That file is larger than 2 MB. Split it or remove extra columns.")
    if not content.strip():
        raise ValidationFailed("That file is empty.")
    rows, invalid = service.parse_upload(file.filename or "upload.csv", content)
    if not rows and not invalid:
        raise ValidationFailed("We couldn't find any staff IDs in that file.")
    report = await service.import_ids(session, workgroup, rows, invalid, user)
    await session.commit()
    return {"report": report.as_dict(), "summary": await _ids_summary(session, workgroup)}


@router.post("/staff-ids/paste")
async def paste_ids(body: PasteIdsIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    rows, invalid = service.parse_pasted(body.text)
    if not rows and not invalid:
        raise ValidationFailed("Paste at least one staff ID.")
    report = await service.import_ids(session, workgroup, rows, invalid, user)
    await session.commit()
    return {"report": report.as_dict(), "summary": await _ids_summary(session, workgroup)}


@router.post("/staff-ids/delete-unclaimed")
async def delete_unclaimed(body: StaffIdsIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    count = await service.delete_unclaimed(session, workgroup, user, body.staff_ids)
    await session.commit()
    return {"deleted": count, "summary": await _ids_summary(session, workgroup)}


@router.get("/staff-ids/export")
async def export_ids(workgroup: OwnedWorkgroup, session: SessionDep, format: Literal["csv", "xlsx"] = "csv") -> Response:
    header, rows = await service.export_rows(session, workgroup.id, only_ids=True)
    name = f"{_slug(workgroup.name)}-staff-ids-{utcnow():%Y%m%d}"
    if format == "xlsx":
        return _download(service.to_xlsx(header, rows, "Staff IDs"), f"{name}.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return _download(service.to_csv(header, rows), f"{name}.csv", "text/csv; charset=utf-8")


# ------------------------------------------------------------------ roles
@router.get("/roles")
async def list_roles(workgroup: OwnedWorkgroup, session: SessionDep) -> list[dict[str, Any]]:
    return await roles.list_roles(session, workgroup.id)


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(body: RoleIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    role = await roles.create_role(session, workgroup, user, body.name, body.salary_kobo, body.description)
    await session.commit()
    return roles.role_out(role)


@router.patch("/roles/{role_id}")
async def update_role(role_id: uuid.UUID, body: RoleUpdateIn, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> dict[str, Any]:
    role = await roles.get_role(session, workgroup.id, role_id)
    await roles.update_role(session, workgroup, role, user, body.model_dump(exclude_unset=True))
    await session.commit()
    return roles.role_out(role)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: uuid.UUID, workgroup: OwnedWorkgroup, user: Manager, session: SessionDep) -> Response:
    role = await roles.get_role(session, workgroup.id, role_id)
    await roles.delete_role(session, workgroup, role, user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
