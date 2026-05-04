from src.agents.agent_base import AgentResult, BaseAgent
from src.tools import database


class AnalyticsAgent(BaseAgent):
    name = "analytics"

    def handle(self, state: dict) -> AgentResult:
        database.log_event(state.get("user_id", ""), "analytics", state.get("query", ""))
        return AgentResult(response="Analytics event logged.")
