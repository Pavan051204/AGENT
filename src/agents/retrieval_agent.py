from typing import Optional

from groq import Groq
from src.agents.agent_base import AgentResult, BaseAgent
from src.settings import get_config
from src.tools.vector_store import VectorStore


class RAGAgent(BaseAgent):
    name = "rag"

    def __init__(self):
        super().__init__()
        config = get_config()

        # Primary: Groq (fast, generous free tier)
        self.groq_client = Groq(api_key=config.groq_api_key) if config.groq_api_key else None
        self.groq_model = config.groq_model
        self.model = self.groq_model  # default display name

        self.vector_store = VectorStore(
            config.app_db_path.replace("app.db", "vector_store")
        )

    def handle(self, state: dict) -> AgentResult:
        query = state.get("query", "")
        role = state.get("role", "")

        # Retrieve relevant documents via local TF-IDF
        results = self.vector_store.query(query, k=5, role=role)

        if not results:
            return AgentResult(response="No relevant documents found in policy database.")

        # Build context from retrieved documents
        context = "\n\n".join(
            [f"**From {doc.metadata.get('source', 'Unknown')}:**\n{doc.content}" for doc in results]
        )

        prompt = f"""You are a helpful company policy assistant. Based on the policy documents provided, answer the user's question concisely and accurately.

COMPANY POLICIES:
{context}

USER QUESTION: {query}

Please provide a clear, direct answer based on the policies. If the information is not in the provided documents, say so explicitly."""

        # Use Groq
        if self.groq_client:
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful company policy assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    model=self.groq_model,
                    temperature=0.7,
                    max_tokens=1024,
                )
                answer = chat_completion.choices[0].message.content
                self.model = self.groq_model
                return AgentResult(response=answer)
            except Exception as e:
                return AgentResult(response=f"Error generating response: {e}")

        return AgentResult(response="No LLM configured. Please set GROQ_API_KEY in .env")


def ingest_documents(*args, **kwargs):
    """Stub for compatibility"""
    pass
