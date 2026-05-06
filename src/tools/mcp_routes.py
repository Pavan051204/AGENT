from typing import Any

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.settings import get_config
from src.tools import database

router = APIRouter(prefix="/tools")


class LeaveRequest(BaseModel):
    user_id: str
    start_date: str
    end_date: str
    reason: str = ""


class TicketRequest(BaseModel):
    user_id: str
    issue_type: str
    description: str = ""
    priority: str = "medium"


class AssetRequest(BaseModel):
    user_id: str
    asset_type: str
    justification: str = ""


class EmailRequest(BaseModel):
    to: str
    subject: str
    body: str


@router.post("/apply_leave")
async def apply_leave(req: LeaveRequest) -> dict[str, Any]:
    result = database.apply_leave(req.user_id, req.start_date, req.end_date, req.reason)
    return {"request_id": result.request_id, "approval_required": result.approval_required}


@router.post("/create_ticket")
async def create_ticket(req: TicketRequest) -> dict[str, Any]:
    ticket_id = database.create_ticket(req.user_id, req.issue_type, req.priority, req.description)
    return {"ticket_id": ticket_id}


@router.post("/request_asset")
async def request_asset(req: AssetRequest) -> dict[str, Any]:
    asset_id = database.request_asset(req.user_id, req.asset_type, req.justification)
    return {"asset_id": asset_id, "approval_required": True}


@router.get("/get_leave_balance")
async def get_leave_balance(user_id: str) -> dict[str, Any]:
    balance = database.get_leave_balance(user_id)
    return {"user_id": user_id, "balance": balance}


@router.post("/approve_request")
async def approve_request(approval_id: int, approver_id: str, status: str) -> dict[str, Any]:
    database.approve_request(approval_id, approver_id, status)
    return {"approval_id": approval_id, "status": status}


@router.post("/send_email")
async def send_email(req: EmailRequest) -> dict[str, Any]:
    config = get_config()
    if not config.power_automate_email_url:
        return {"status": "skipped", "detail": "POWER_AUTOMATE_EMAIL_URL not set"}

    payload = {"to": req.to, "subject": req.subject, "body": req.body}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(config.power_automate_email_url, json=payload)

    return {"status": "sent", "code": response.status_code}


class CancelLeaveRequest(BaseModel):
    leave_id: int
    user_id: str


@router.post("/cancel_leave")
async def cancel_leave(req: CancelLeaveRequest) -> dict[str, Any]:
    result = database.cancel_leave(req.leave_id, req.user_id)
    return {"message": result, "success": "cancelled" in result.lower()}


@router.get("/list_leaves")
async def list_leaves(user_id: str) -> dict[str, Any]:
    leaves = database.list_leaves(user_id)
    return {"user_id": user_id, "leaves": leaves}


@router.get("/pending_leaves")
async def get_pending_leaves(user_id: str) -> dict[str, Any]:
    pending = database.get_pending_leaves(user_id)
    return {"user_id": user_id, "pending_leaves": pending}


@router.get("/list_tickets")
async def list_tickets(user_id: str) -> dict[str, Any]:
    tickets = database.list_tickets(user_id)
    return {"user_id": user_id, "tickets": tickets}


@router.get("/list_assets")
async def list_assets(user_id: str) -> dict[str, Any]:
    assets = database.list_assets(user_id)
    return {"user_id": user_id, "assets": assets}


@router.get("/inventory_status")
async def inventory_status() -> dict[str, Any]:
    items = []
    for key, stock in database.INVENTORY.items():
        items.append({"type": key, "available": stock["available"], "total": stock["total"]})
    return {"items": items}


@router.get("/maintenance_schedule")
async def maintenance_schedule() -> dict[str, Any]:
    return {"maintenance": database.get_planned_maintenance()}


@router.get("/active_outages")
async def active_outages() -> dict[str, Any]:
    return {"outages": database.get_active_outages()}
