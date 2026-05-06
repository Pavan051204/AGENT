# Enterprise Multi-Agent AI Copilot - Policy Assistant

This project implements an enterprise policy assistant using Gemini API with PDF-based RAG (Retrieval-Augmented Generation). It automatically indexes all PDF documents in the `docs` folder and provides policy answers through a web interface.

## Features
- **Gemini-Powered**: Uses the best available Gemini model automatically
- **PDF RAG**: Automatically extracts and indexes policy documents from the docs folder
- **Web UI**: Clean, responsive chat interface for policy queries
- **Role-Based**: Support for different employee roles (HR, Finance, IT, etc.)
- **Session Management**: Persistent conversation history and user preferences

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables** (`.env` file is already configured):
   ```
   GEMINI_API_KEY=AIzaSyBzNrVRjfq81EnX59bHZxeGAxSYE7Bsm0Y
   GEMINI_MODEL=auto
   PDF_DOCS_PATH=./docs
   ```

3. **Run the application:**
   ```bash
   uvicorn src.main:app --reload
   ```

4. **Access the UI:**
   - Open browser to `http://localhost:8000`
   - The system automatically ingests PDFs from the `docs` folder on startup

## How It Works

### PDF Ingestion
- All `.pdf` files in the `docs` folder are automatically processed on app startup
- Text is extracted from PDFs and split into manageable chunks
- Chunks are indexed using a simple vector store for fast retrieval

### Query Processing
1. User asks a policy question
2. The system retrieves relevant PDF chunks (RAG)
3. Gemini generates a contextual answer based on the retrieved documents
4. Response is displayed in the chat UI with source attribution

### Supported Query Types
- **Leave Policies**: Vacation, sick leave, maternity, approval process
- **Travel**: Travel guidelines, reimbursement, visa policies
- **Financial**: Salary advance, payslip, variable pay
- **HR Policies**: Code of conduct, asset damage, team policies
- **Benefits**: Employee discounts, CSR policies, other benefits

## Architecture

```
src/
├── main.py                    # FastAPI entry point
├── settings.py                # Configuration (Gemini API key, paths)
├── agents/
│   ├── retrieval_agent.py    # RAG agent using Gemini API
│   └── agent_registry.py      # Agent routing
├── tools/
│   ├── pdf_ingest.py         # PDF extraction and ingestion
│   ├── vector_store.py        # Document storage and retrieval
│   └── mcp_routes.py          # Tool endpoints
├── orchestration/
│   └── workflow.py            # LangGraph workflow
└── web/static/                # UI (HTML, CSS, JS)

docs/
├── Novigo Leave Policy.pdf
├── Novigo-Travel Guidelines.pdf
├── CSR policy_Novigo.pdf
├── ... (12+ policy PDFs)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Your Google Generative AI API key |
| `GEMINI_MODEL` | `auto` | Gemini model to use (auto picks the best available) |
| `RATE_LIMIT_GEMINI` | `60` | Requests per minute |
| `PDF_DOCS_PATH` | `./docs` | Path to PDF documents |
| `APP_DB_PATH` | `./data/app.db` | SQLite database path |

## API Endpoints

### `POST /chat`
Ask a policy question.

**Request:**
```json
{
  "user_id": "emp-123",
  "role": "employee",
  "query": "What is the leave policy?",
  "session_id": "sess-abc"
}
```

**Response:**
```json
{
  "response": "Based on the Novigo Leave Policy...",
  "trace_id": "trace_abc123",
  "approval_required": false
}
```

### `GET /health`
Check API health status.

## Adding New PDFs

1. Add PDF files to the `docs/` folder
2. Restart the application - PDFs are automatically ingested on startup
3. Ask questions about the new policies!

## Troubleshooting

### "No relevant documents found"
- Check if PDFs are in the `docs` folder
- Verify PDFs have readable text (not image-only)
- Ask more specific questions related to policy keywords

### "Error generating response"
- Verify `GEMINI_API_KEY` is set correctly
- Check internet connection
- Ensure API quota is not exceeded

### Slow responses
- Gemini 1.5-Flash is optimized for speed
- Reduce chunk size in `pdf_ingest.py` if needed
- Consider caching frequently asked questions

## Technologies

- **Framework**: FastAPI
- **AI Model**: Google Gemini 1.5-Flash
- **Workflow**: LangGraph
- **PDF Processing**: PyPDF
- **Frontend**: Vanilla JavaScript
- **Database**: SQLite

## License

Internal use only.
