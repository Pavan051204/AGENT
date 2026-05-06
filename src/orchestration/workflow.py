from typing import Literal, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from src.agents.agent_registry import AGENT_REGISTRY
from src.core.access_control import check_access
from src.core.memory_manager import MemoryManager
from src.tools import database

memory_manager = MemoryManager()


class GraphState(TypedDict, total=False):
    user_id: str
    role: str
    query: str
    session_id: str
    response: str
    approval_required: bool
    trace_id: str
    model_used: str
    model_preference: str
    intent: str
    chat_history: list


# ---------------------------------------------------------------------------
# Intent keywords — lightweight classification without an LLM call
# ---------------------------------------------------------------------------

_HR_LEAVE_KEYWORDS = [
    "leave", "apply leave", "cancel leave", "leave balance", "leave history",
    "pending leave", "leave status", "approval status", "holiday", "calendar",
    "day off", "time off", "vacation", "sick leave", "casual leave",
    "approvals", "pending approvals", "my approvals", "approve", "reject",
]

_HR_POLICY_KEYWORDS = [
    "policy", "handbook", "guideline", "notice period", "work from home",
    "wfh", "maternity", "paternity", "probation", "code of conduct",
    "dress code", "appraisal", "performance review", "resignation",
    "termination", "onboarding", "benefits", "insurance", "gratuity",
]

_IT_KEYWORDS = [
    "ticket", "laptop", "vpn", "printer", "outlook", "email issue",
    "network", "software install", "it support", "it help", "asset",
    "monitor", "keyboard", "mouse", "license", "password reset",
    "access request", "hardware", "it request", "raise ticket",
    "create ticket", "my tickets", "it ticket", "assign ticket",
    "resolve ticket", "maintenance", "outage", "inventory",
    "asset request", "vpn token", "software license",
    "it issue", "it problem", "tech support",
]

_FINANCE_KEYWORDS = [
    "payslip", "salary", "reimbursement", "reimburse", "claim",
    "tax", "pf", "provident fund", "ctc", "investment", "declaration",
    "payroll", "expense", "receipt", "finance request",
]


def _classify_intent(query: str) -> str:
    """Keyword-based intent classification.

    Returns one of: hr-leave, hr-policy, it, finance, general.
    Uses a simple scoring approach — whichever category has the most
    keyword matches wins.
    """
    q = query.lower()

    scores = {
        "hr-leave": 0,
        "hr-policy": 0,
        "it": 0,
        "finance": 0,
    }

    # Direct match for common HR requests
    if any(k in q for k in [
        "pending approvals", "show approvals", "my approvals",
        "pending request", "approve it", "reject it",
        "apply leave", "take leave", "want leave", "need leave",
        "leave balance", "leave history", "cancel leave",
        "sick leave", "casual leave", "earned leave", "comp off",
        "i am sick", "i am ill", "feeling sick", "not feeling well",
        "feverish", "fever", "unwell",
    ]):
        return "hr-leave"

    for kw in _HR_LEAVE_KEYWORDS:
        if kw in q:
            scores["hr-leave"] += 1

    for kw in _HR_POLICY_KEYWORDS:
        if kw in q:
            scores["hr-policy"] += 1

    for kw in _IT_KEYWORDS:
        if kw in q:
            scores["it"] += 1

    for kw in _FINANCE_KEYWORDS:
        if kw in q:
            scores["finance"] += 1

    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] == 0:
        return "general"
    return best


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------

def _intent_detection(state: GraphState) -> GraphState:
    """Node 1 — detect intent from the user query."""
    intent = _classify_intent(state["query"])
    state["intent"] = intent
    database.log_event(state["user_id"], "intent_detected", f"intent={intent} query={state['query'][:100]}")
    return state


def _role_validation(state: GraphState) -> GraphState:
    """Node 2 — validate that the user's role is allowed for this intent."""
    intent = state.get("intent", "general")

    # Map sub-intents to top-level access categories
    access_map = {
        "hr-leave": "hr",
        "hr-policy": "hr",
        "it": "it",
        "finance": "finance",
        "general": "general",
    }
    access_category = access_map.get(intent, "general")

    if not check_access(state["role"], access_category):
        state["response"] = (
            f"🔒 **Access Denied**\n\n"
            f"Your role **{state['role']}** does not have access to **{access_category}** operations.\n"
            "Please contact your administrator if you believe this is an error."
        )
        state["intent"] = "blocked"

    return state


def _route_agent(state: GraphState) -> str:
    """Conditional edge — decide which agent to run based on intent."""
    intent = state.get("intent", "general")
    route_map = {
        "hr-leave": "hr_agent",
        "hr-policy": "rag_agent",
        "it": "it_agent",
        "finance": "finance_agent",
        "general": "rag_agent",
        "blocked": "respond",
    }
    return route_map.get(intent, "rag_agent")


def _hr_agent(state: GraphState) -> GraphState:
    """HR Agent node — handles leave management."""
    agent = AGENT_REGISTRY.get("hr")
    state["chat_history"] = memory_manager.get_context(state["session_id"])
    result = agent.handle(state)
    state["response"] = result.response
    state["approval_required"] = result.approval_required
    state["model_used"] = getattr(agent, "model", "hr-agent")
    return state


def _rag_agent(state: GraphState) -> GraphState:
    """RAG Agent node — policy questions and general queries."""
    agent = AGENT_REGISTRY.get("rag")
    state["chat_history"] = memory_manager.get_context(state["session_id"])
    result = agent.handle(state)
    state["response"] = result.response
    state["approval_required"] = result.approval_required
    if hasattr(agent, "model"):
        state["model_used"] = agent.model
    return state


def _it_agent(state: GraphState) -> GraphState:
    """IT Agent node — ticket, asset, and IT operations management."""
    agent = AGENT_REGISTRY.get("it")
    state["chat_history"] = memory_manager.get_context(state["session_id"])
    result = agent.handle(state)
    state["response"] = result.response
    state["approval_required"] = result.approval_required
    state["model_used"] = getattr(agent, "model", "it-agent")
    return state


def _finance_agent(state: GraphState) -> GraphState:
    """Finance Agent node — payslip, reimbursement, tax queries."""
    agent = AGENT_REGISTRY.get("finance")
    result = agent.handle(state)
    state["response"] = result.response
    state["approval_required"] = result.approval_required
    state["model_used"] = "finance-agent"
    return state


def _respond(state: GraphState) -> GraphState:
    """Pass-through node for blocked/pre-set responses."""
    return state


def _memory(state: GraphState) -> GraphState:
    """Save conversation to short-term and long-term memory."""
    memory_manager.add_message(
        state["session_id"],
        {"role": state["role"], "query": state["query"], "response": state["response"]},
    )
    memory_manager.save_long_term(state["user_id"], state["session_id"], state["query"])
    return state


def _log_trace(state: GraphState) -> GraphState:
    """Log the full trace of this request."""
    database.log_event(
        state["user_id"],
        "chat_response",
        f"trace={state.get('trace_id', '')} intent={state.get('intent', '')} "
        f"model={state.get('model_used', '')} approval={state.get('approval_required', False)}",
    )
    return state


# ---------------------------------------------------------------------------
# Build the LangGraph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Build the multi-agent LangGraph workflow.

    Flow:
        User Query
         → intent_detection
         → role_validation
         → [conditional] route to correct agent (hr / rag / it / finance / respond)
         → memory
         → log_trace
         → END
    """
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("intent_detection", _intent_detection)
    graph.add_node("role_validation", _role_validation)
    graph.add_node("hr_agent", _hr_agent)
    graph.add_node("rag_agent", _rag_agent)
    graph.add_node("it_agent", _it_agent)
    graph.add_node("finance_agent", _finance_agent)
    graph.add_node("respond", _respond)
    graph.add_node("memory", _memory)
    graph.add_node("log_trace", _log_trace)

    # Edges
    graph.set_entry_point("intent_detection")
    graph.add_edge("intent_detection", "role_validation")

    # Conditional routing after role validation
    graph.add_conditional_edges(
        "role_validation",
        _route_agent,
        {
            "hr_agent": "hr_agent",
            "rag_agent": "rag_agent",
            "it_agent": "it_agent",
            "finance_agent": "finance_agent",
            "respond": "respond",
        },
    )

    # All agents converge to memory → log → END
    graph.add_edge("hr_agent", "memory")
    graph.add_edge("rag_agent", "memory")
    graph.add_edge("it_agent", "memory")
    graph.add_edge("finance_agent", "memory")
    graph.add_edge("respond", "memory")
    graph.add_edge("memory", "log_trace")
    graph.add_edge("log_trace", END)

    return graph.compile()


def run_graph(user_id: str, role: str, query: str, session_id: str, model_preference: str = "gemini") -> GraphState:
    graph = build_graph()
    trace_id = f"trace_{uuid4().hex[:8]}"
    initial_state: GraphState = {
        "user_id": user_id,
        "role": role,
        "query": query,
        "session_id": session_id,
        "trace_id": trace_id,
        "approval_required": False,
        "model_preference": model_preference,
        "intent": "",
    }
    result = graph.invoke(initial_state)
    result["trace_id"] = trace_id
    return result
