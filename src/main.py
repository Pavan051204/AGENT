from pathlib import Path

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
    update_leave_status, list_leaves, get_pending_leaves,
    cancel_leave, get_leave_balance, get_all_leaves,
    get_hr_users, get_approvals_for_hr,
    deduct_leave_balance, restore_leave_balance,
    count_working_days, _get_conn,
)
from src.tools.pdf_ingest import ingest_pdfs


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "employee"


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    success: bool
    token: str = ""
    username: str = ""
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
        password = req.password.strip()
        role = req.role.strip().lower()

        if not username or not password:
            return AuthResponse(success=False, message="Username and password are required.")

        if len(username) < 3:
            return AuthResponse(success=False, message="Username must be at least 3 characters.")

        if len(password) < 4:
            return AuthResponse(success=False, message="Password must be at least 4 characters.")

        if role not in VALID_ROLES:
            return AuthResponse(success=False, message=f"Invalid role. Choose from: {', '.join(VALID_ROLES)}")

        # Check if user already exists
        existing = get_user_by_username(username)
        if existing:
            return AuthResponse(success=False, message="Username already exists.")

        password_hash = hash_password(password)
        user_id = create_user(username, password_hash, role)

        if user_id is None:
            return AuthResponse(success=False, message="Registration failed. Please try again.")

        token = create_token(str(user_id), username, role)
        return AuthResponse(
            success=True,
            token=token,
            username=username,
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
            role=user["role"],
            message="Login successful!",
        )

    @app.get("/auth/me")
    def me(current_user: dict = Depends(get_current_user)) -> dict:
        """Return information about the currently authenticated user."""
        return {
            "user_id": current_user["user_id"],
            "username": current_user["username"],
            "role": current_user["role"],
        }

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
        result = run_graph(
            user_id=req.user_id,
            role=current_user["role"],  # Use role from token, not from request
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
        """Get pending approvals.  HR sees their assigned; manager/admin see all."""
        role = current_user["role"]
        username = current_user["username"]
        if role not in ("manager", "hr", "admin"):
            return {"error": "Access denied. Only managers, HR, and admins can view approvals.", "approvals": []}

        if role == "hr":
            # HR sees only approvals assigned to them
            approvals = get_approvals_for_hr(username)
        else:
            approvals = get_pending_approvals(role)

        enriched = []
        for a in approvals:
            item = dict(a)
            if a["request_type"] == "leave":
                leave = get_leave_by_id(a["request_id"])
                if leave:
                    item["leave_details"] = leave
            enriched.append(item)
        return {"approvals": enriched}

    @app.post("/api/approvals/{approval_id}/decide")
    def decide_approval(
        approval_id: int,
        decision: ApprovalDecision,
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        """Approve or reject a pending request.  Syncs leave status and balance."""
        role = current_user["role"]
        if role not in ("manager", "hr", "admin"):
            return {"error": "Access denied."}

        if decision.status not in ("approved", "rejected"):
            return {"error": "Status must be 'approved' or 'rejected'."}

        # Update the approval record
        approve_request(approval_id, current_user["user_id"], decision.status)

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
                update_leave_status(req_id, decision.status)
                leave = get_leave_by_id(req_id)
                if leave and decision.status == "approved":
                    # Deduct from leave balance
                    days = count_working_days(leave["start_date"], leave["end_date"])
                    leave_type = leave.get("leave_type", "casual") or "casual"
                    deduct_leave_balance(leave["user_id"], leave_type, days)
                elif leave and decision.status == "rejected":
                    pass  # No deduction needed for rejected

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
        user_id = current_user["user_id"]
        if role in ("hr", "admin"):
            leaves = get_all_leaves()
        else:
            leaves = list_leaves(user_id)
        return {"leaves": leaves}

    @app.get("/api/leaves/pending")
    def get_my_pending_leaves(current_user: dict = Depends(get_current_user)) -> dict:
        """Get current user's pending leave requests."""
        pending = get_pending_leaves(current_user["user_id"])
        return {"pending_leaves": pending}

    @app.get("/api/leaves/balance")
    def get_my_leave_balance(current_user: dict = Depends(get_current_user)) -> dict:
        """Get current user's leave balance (all types)."""
        balance = get_leave_balance(current_user["user_id"])
        return {"user_id": current_user["user_id"], "balance": balance}

    @app.post("/api/leaves/{leave_id}/cancel")
    def cancel_my_leave(leave_id: int, current_user: dict = Depends(get_current_user)) -> dict:
        """Cancel a pending leave request."""
        result = cancel_leave(leave_id, current_user["user_id"])
        success = "cancelled" in result.lower()
        return {"success": success, "message": result}

    # ------------------------------------------------------------------
    # HR Users API
    # ------------------------------------------------------------------

    @app.get("/api/hr-users")
    def list_hr_users() -> dict:
        """Get all HR users (for leave assignment dropdown). Public endpoint."""
        return {"hr_users": get_hr_users()}

    return app


app = create_app()
