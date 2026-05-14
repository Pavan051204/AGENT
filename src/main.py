from pathlib import Path
import re

from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.settings import get_config
from src.core.logging_setup import setup_logging
from src.core.auth import hash_password, verify_password, create_token, decode_token, get_current_user
from src.orchestration.workflow import run_graph
from src.tools.mcp_routes import router as tools_router
from src.tools.database import (
    init_db, create_user, get_user_by_username,
    get_pending_approvals, approve_request, get_leave_by_id,
    process_leave_decision, list_leaves, get_pending_leaves,
    cancel_leave, get_leave_balance, get_all_leaves,
    get_hr_users, get_approvals_for_hr,
    _get_conn,
    # IT-specific
    get_ticket_by_id, list_tickets, get_all_tickets,
    get_open_tickets_for_user, get_it_pending_approvals,
    assign_ticket, resolve_ticket, update_ticket_status,
    get_asset_by_id, list_assets, get_all_assets,
    update_asset_status, get_it_users,
)
from src.tools.pdf_ingest import ingest_pdfs


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "employee"


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    token: str = ""
    username: str = ""
    email: str = ""
    role: str = ""
    message: str = ""


class ChatRequest(BaseModel):
    user_id: str
    role: str
    query: str
    session_id: str
    model_preference: str = "gemini"


class ChatResponse(BaseModel):
    response: str
    trace_id: str
    approval_required: bool
    model_used: str = ""


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

VALID_ROLES = ["employee", "manager", "hr", "it", "finance", "admin"]

_RESERVED_EMAIL_DOMAINS = {"example.com", "example.org", "example.net"}


def _is_valid_email(email: str) -> bool:
    email = (email or "").strip()
    if not email:
        return False
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return False
    domain = email.rsplit("@", 1)[-1].lower()
    if domain in _RESERVED_EMAIL_DOMAINS:
        return False
    return True


def create_app() -> FastAPI:
    setup_logging()
    init_db()

    # Ingest PDFs on startup (Disabled for large documents, run manually if needed)
    # try:
    #     ingest_pdfs()
    # except Exception as e:
    #     print(f"Warning: Failed to ingest PDFs: {e}")

    app = FastAPI(title=get_config().app_name)
    app.include_router(tools_router)

    static_dir = Path(__file__).resolve().parent / "web" / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ------------------------------------------------------------------
    # Auth routes
    # ------------------------------------------------------------------

    @app.post("/auth/register", response_model=AuthResponse)
    def register(req: RegisterRequest) -> AuthResponse:
        """Create a new user account."""
        username = req.username.strip()
        email = req.email.strip()
        password = req.password.strip()
        role = req.role.strip().lower()

        if not username or not email or not password:
            return AuthResponse(success=False, message="Username, email, and password are required.")

        if len(username) < 3:
            return AuthResponse(success=False, message="Username must be at least 3 characters.")

        if len(password) < 4:
            return AuthResponse(success=False, message="Password must be at least 4 characters.")

        if not _is_valid_email(email):
            return AuthResponse(success=False, message="Please enter a valid email address.")

        if role not in VALID_ROLES:
            return AuthResponse(success=False, message=f"Invalid role. Choose from: {', '.join(VALID_ROLES)}")

        # Check if user already exists
        existing = get_user_by_username(username)
        if existing:
            return AuthResponse(success=False, message="Username already exists.")

        password_hash = hash_password(password)
        user_id = create_user(username, email, password_hash, role)

        if user_id is None:
            return AuthResponse(success=False, message="Registration failed. Username or email may already exist.")

        token = create_token(str(user_id), username, role)
        return AuthResponse(
            success=True,
            token=token,
            username=username,
            email=email,
            role=role,
            message="Account created successfully!",
        )

    @app.post("/auth/login", response_model=AuthResponse)
    def login(req: LoginRequest) -> AuthResponse:
        """Authenticate an existing user."""
        username = req.username.strip()
        password = req.password.strip()

        if not username or not password:
            return AuthResponse(success=False, message="Username and password are required.")

        user = get_user_by_username(username)
        if user is None:
            return AuthResponse(success=False, message="Invalid username or password.")

        if not verify_password(password, user["password_hash"]):
            return AuthResponse(success=False, message="Invalid username or password.")

        token = create_token(str(user["id"]), user["username"], user["role"])
        return AuthResponse(
            success=True,
            token=token,
            username=user["username"],
            email=user.get("email", ""),
            role=user["role"],
            message="Login successful!",
        )

    @app.get("/auth/me")
    def me(current_user: dict = Depends(get_current_user)) -> dict:
        """Return information about the currently authenticated user."""
        user = get_user_by_username(current_user["username"])
        email = user.get("email", "") if user else ""
        return {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "email": email,
            "role": current_user["role"],
        }

    class UpdateEmailRequest(BaseModel):
        email: str

    @app.post("/api/profile/email")
    def update_my_email(req: UpdateEmailRequest, current_user: dict = Depends(get_current_user)) -> dict:
        """Update the logged-in user's email address (used for notifications)."""
        new_email = (req.email or "").strip()
        if not _is_valid_email(new_email):
            return {"success": False, "message": "Please enter a valid email address."}

        conn = _get_conn()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE users SET email = ? WHERE username = ?", (new_email, current_user["username"]))
            conn.commit()
            if cur.rowcount == 0:
                return {"success": False, "message": "User not found."}
            return {"success": True, "email": new_email}
        except Exception:
            conn.rollback()
            return {"success": False, "message": "Email update failed. Email may already be in use."}
        finally:
            conn.close()

    class ChangePasswordRequest(BaseModel):
        old_password: str
        new_password: str

    @app.post("/auth/change-password")
    def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)) -> dict:
        user = get_user_by_username(current_user["username"])
        if not user:
            return {"success": False, "message": "User not found."}
        if not verify_password(req.old_password, user["password_hash"]):
            return {"success": False, "message": "Incorrect old password."}
        
        new_hash = hash_password(req.new_password)
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Password updated successfully!"}

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def login_page() -> FileResponse:
        """Serve the login / register page as the landing page."""
        return FileResponse(static_dir / "login.html")

    @app.get("/chat")
    def chat_page() -> FileResponse:
        """Serve the chat UI (requires auth on the client side)."""
        return FileResponse(static_dir / "index.html")

    @app.get("/ui")
    def ui_page() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    # ------------------------------------------------------------------
    # Chat API
    # ------------------------------------------------------------------

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(req: ChatRequest, current_user: dict = Depends(get_current_user)) -> ChatResponse:
        """Chat endpoint – requires a valid JWT token."""
        # Standardize: Use current_user["username"] for business logic/DB records
        # instead of the client-provided user_id which might be inconsistent.
        user_id_to_use = current_user["username"]
        
        result = run_graph(
            user_id=user_id_to_use,
            role=current_user["role"],
            query=req.query,
            session_id=req.session_id,
            model_preference=req.model_preference,
        )
        return ChatResponse(
            response=result["response"],
            trace_id=result["trace_id"],
            approval_required=result["approval_required"],
            model_used=result.get("model_used", ""),
        )

    # ------------------------------------------------------------------
    # Approval Management API
    # ------------------------------------------------------------------

    class ApprovalDecision(BaseModel):
        status: str  # "approved" or "rejected"

    @app.get("/api/approvals/pending")
    def pending_approvals(current_user: dict = Depends(get_current_user)) -> dict:
        """Get pending approvals.  HR sees leave; IT sees tickets/assets; manager/admin see all."""
        role = current_user["role"]
        username = current_user["username"]
        if role not in ("manager", "hr", "it", "admin"):
            return {"error": "Access denied. Only managers, HR, IT, and admins can view approvals.", "approvals": []}

        if role == "hr":
            approvals = get_approvals_for_hr(username)
        elif role == "it":
            approvals = get_it_pending_approvals()
        else:
            approvals = get_pending_approvals(role)

        enriched = []
        for a in approvals:
            item = dict(a)
            if a["request_type"] == "leave":
                leave = get_leave_by_id(a["request_id"])
                if leave:
                    item["leave_details"] = leave
            elif a["request_type"] == "ticket":
                ticket = get_ticket_by_id(a["request_id"])
                if ticket:
                    item["ticket_details"] = ticket
            elif a["request_type"] == "asset":
                asset = get_asset_by_id(a["request_id"])
                if asset:
                    item["asset_details"] = asset
            enriched.append(item)
        return {"approvals": enriched}

    @app.post("/api/approvals/{approval_id}/decide")
    def decide_approval(
        approval_id: int,
        decision: ApprovalDecision,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        """Approve or reject a pending request.  Syncs leave/ticket/asset status."""
        role = current_user["role"]
        if role not in ("manager", "hr", "it", "admin"):
            return {"error": "Access denied."}

        if decision.status not in ("approved", "rejected"):
            return {"error": "Status must be 'approved' or 'rejected'."}

        # Update the approval record
        approve_request(approval_id, current_user["username"], decision.status)

        # Find the underlying request
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT request_type, request_id FROM approvals WHERE id = ?",
            (approval_id,),
        )
        row = cur.fetchone()
        conn.close()

        if row:
            req_type, req_id = row
            if req_type == "leave":
                # Centralized leave decision logic (also triggers Power Automate notification)
                process_leave_decision(req_id, decision.status, current_user["username"])
            elif req_type == "ticket":
                new_status = "in_progress" if decision.status == "approved" else "closed"
                update_ticket_status(req_id, new_status)
            elif req_type == "asset":
                update_asset_status(req_id, decision.status)

        return {
            "approval_id": approval_id,
            "status": decision.status,
            "approved_by": current_user["username"],
        }

    # ------------------------------------------------------------------
    # Leave Management API (REST endpoints)
    # ------------------------------------------------------------------

    @app.get("/api/leaves")
    def get_leaves(current_user: dict = Depends(get_current_user)) -> dict:
        """Get leave records. Employees see own; HR/admin see all."""
        role = current_user["role"]
        username = current_user["username"]
        if role in ("hr", "admin"):
            leaves = get_all_leaves()
        else:
            leaves = list_leaves(username)
        return {"leaves": leaves}

    @app.get("/api/leaves/pending")
    def get_my_pending_leaves(current_user: dict = Depends(get_current_user)) -> dict:
        """Get current user's pending leave requests."""
        username = current_user["username"]
        pending = get_pending_leaves(username)
        return {"pending_leaves": pending}

    @app.get("/api/leaves/balance")
    def get_my_leave_balance(current_user: dict = Depends(get_current_user)) -> dict:
        """Get current user's leave balance (all types)."""
        username = current_user["username"]
        balance = get_leave_balance(username)
        return {"user_id": username, "balance": balance}

    @app.post("/api/leaves/{leave_id}/cancel")
    def cancel_my_leave(leave_id: int, current_user: dict = Depends(get_current_user)) -> dict:
        """Cancel a pending leave request."""
        result = cancel_leave(leave_id, current_user["username"])
        success = "cancelled" in result.lower()
        return {"success": success, "message": result}

    # ------------------------------------------------------------------
    # HR Users API
    # ------------------------------------------------------------------

    @app.get("/api/hr-users")
    def list_hr_users() -> dict:
        """Get all HR users (for leave assignment dropdown). Public endpoint."""
        return {"hr_users": get_hr_users()}

    # ------------------------------------------------------------------
    # IT Tickets API (REST endpoints)
    # ------------------------------------------------------------------

    @app.get("/api/tickets")
    def get_tickets(current_user: dict = Depends(get_current_user)) -> dict:
        """Get IT tickets. Employees see own; IT/admin see all."""
        role = current_user["role"]
        username = current_user["username"]
        if role in ("it", "admin"):
            tickets = get_all_tickets()
        else:
            tickets = list_tickets(username)
        return {"tickets": tickets}

    @app.get("/api/tickets/open")
    def get_my_open_tickets(current_user: dict = Depends(get_current_user)) -> dict:
        """Get current user's open tickets."""
        username = current_user["username"]
        tickets = get_open_tickets_for_user(username)
        return {"tickets": tickets}

    @app.post("/api/tickets/{ticket_id}/resolve")
    def resolve_ticket_endpoint(ticket_id: int, current_user: dict = Depends(get_current_user)) -> dict:
        """Resolve a ticket. IT team and admin only."""
        role = current_user["role"]
        if role not in ("it", "admin"):
            return {"error": "Access denied. Only IT team can resolve tickets."}
        result = resolve_ticket(ticket_id, current_user["username"])
        success = "resolved" in result.lower()
        return {"success": success, "message": result}

    class AssignTicketRequest(BaseModel):
        engineer: str

    @app.post("/api/tickets/{ticket_id}/assign")
    def assign_ticket_endpoint(ticket_id: int, req: AssignTicketRequest, current_user: dict = Depends(get_current_user)) -> dict:
        """Assign a ticket to an engineer. IT team and admin only."""
        role = current_user["role"]
        if role not in ("it", "admin"):
            return {"error": "Access denied. Only IT team can assign tickets."}
        result = assign_ticket(ticket_id, req.engineer)
        success = "assigned" in result.lower()
        return {"success": success, "message": result}

    # ------------------------------------------------------------------
    # IT Assets API
    # ------------------------------------------------------------------

    @app.get("/api/assets")
    def get_assets(current_user: dict = Depends(get_current_user)) -> dict:
        """Get asset requests. Employees see own; IT/admin see all."""
        role = current_user["role"]
        username = current_user["username"]
        if role in ("it", "admin"):
            assets = get_all_assets()
        else:
            assets = list_assets(username)
        return {"assets": assets}

    @app.get("/api/it-users")
    def list_it_users() -> dict:
        """Get all IT team users. Public endpoint."""
        return {"it_users": get_it_users()}

    return app


app = create_app()
