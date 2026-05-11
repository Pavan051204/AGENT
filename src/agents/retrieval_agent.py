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
        intent = state.get("intent", "")
        chat_history = state.get("chat_history", [])

        # Retrieve relevant documents via local TF-IDF
        results = self.vector_store.query(query, k=5, role=role)

        # Build context from retrieved documents
        web_search_used = False
        if not results:
            if intent == "general":
                try:
                    from ddgs import DDGS
                    results_web = DDGS().text(query, max_results=3)
                    if results_web:
                        context = "\n\n".join([f"**From {res.get('title', 'Web')}:**\n{res.get('body', '')}" for res in results_web])
                        web_search_used = True
                    else:
                        context = "No specific policy documents found for this query."
                except Exception as e:
                    context = f"No specific policy documents found for this query. (Web search failed: {e})"
            else:
                context = "No specific policy documents found for this query."
        else:
            context = "\n\n".join(
                [f"**From {doc.metadata.get('source', 'Unknown')}:**\n{doc.content}" for doc in results]
            )

        # Build conversation history for context
        history_text = ""
        if chat_history:
            history_text = "CONVERSATION HISTORY:\n"
            for msg in chat_history[-3:]:  # Include last 3 messages for context
                if msg.get("query"):
                    history_text += f"User: {msg['query']}\n"
                if msg.get("response"):
                    history_text += f"Assistant: {msg['response']}\n"
            history_text += "\n"

        if web_search_used:
            prompt = f"""You are Novi Pilot. You assist employees with HR, IT, Finance inquiries.
I couldn't find the answer in our internal company PDFs, so I searched the public web. Answer the user's question based on these web search results. Make sure to mention that this information is from the public internet, not an internal policy.

{history_text}
WEB SEARCH RESULTS:
{context}

USER QUESTION: {query}"""
        else:
            prompt = f"""You are Novi Pilot. You assist employees with HR, IT, Finance inquiries, and general company policies.
If the user says a conversational greeting (like "hi", "hello"), respond politely and ask how you can help.
If the user asks a policy question, answer based ONLY on the provided policy documents below. If the answer is not in the documents, explicitly say "I couldn't find that in the company policies."
If the user asks a general knowledge question (e.g., how to make biryani, sports, history), you may answer it using your general knowledge or the context provided, but mention that this is not a company policy.
Remember the context from our conversation history to provide personalized responses.

{history_text}
COMPANY POLICIES:
{context}

USER QUESTION: {query}"""

        # Use Groq
        if self.groq_client:
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful company policy assistant. Remember context from previous messages in this conversation."},
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
