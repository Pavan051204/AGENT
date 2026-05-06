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

        # Build context from retrieved documents
        if not results:
            context = "No specific policy documents found for this query."
        else:
            context = "\n\n".join(
                [f"**From {doc.metadata.get('source', 'Unknown')}:**\n{doc.content}" for doc in results]
            )

        prompt = f"""You are Novi Pilot. You assist employees with HR, IT, Finance inquiries, and general company policies.
If the user says a conversational greeting (like "hi", "hello"), respond politely and ask how you can help.
If the user asks a policy question, answer based ONLY on the provided policy documents below. If the answer is not in the documents, explicitly say "I couldn't find that in the company policies."

COMPANY POLICIES:
{context}

USER QUESTION: {query}"""

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
