from pathlib import Path

from src.tools.vector_store import Document, VectorStore
from src.settings import get_config
from langchain_text_splitters import RecursiveCharacterTextSplitter

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from PDF file"""
    from pypdf import PdfReader

    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    return text


def ingest_pdfs(docs_path: str | None = None) -> int:
    """Ingest all PDFs from docs folder into vector store"""
    if docs_path is None:
        docs_path = get_config().pdf_docs_path

    vector_store = VectorStore(get_config().app_db_path.replace("app.db", "vector_store"))
    docs_dir = Path(docs_path)

    if not docs_dir.exists():
        print(f"Docs directory not found: {docs_dir}")
        return 0

    documents = []
    pdf_count = 0

    # High-level chunking strategy
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )

    # Map specific policies to roles to enforce RBAC
    role_mapping = {
        "Novigo-Policy-5-VariablePay": ["manager", "hr", "finance", "admin"], # Restricted
        "Corporate Discount": ["employee", "manager", "hr", "admin"],
        "Policy for Employees on Business Visas": ["employee", "manager", "hr", "admin"],
    }

    for pdf_file in docs_dir.glob("*.pdf"):
        print(f"Ingesting {pdf_file.name}...")
        
        # Determine role based on filename mapping
        doc_roles = ["all"] # Default to all
        for key, roles in role_mapping.items():
            if key in pdf_file.name:
                doc_roles = roles
                break

        text = extract_pdf_text(pdf_file)

        if text.strip():
            # Use LangChain's RecursiveCharacterTextSplitter
            chunks = text_splitter.split_text(text)
            for i, chunk in enumerate(chunks):
                doc = Document(
                    content=chunk,
                    metadata={
                        "source": pdf_file.name,
                        "chunk": i,
                        "role": doc_roles,
                    },
                )
                documents.append(doc)
            pdf_count += 1

    print(f"Extracted {len(documents)} chunks from {pdf_count} PDFs. Generating embeddings...")
    vector_store.add_documents(documents)
    print("Ingestion complete.")
    return len(documents)
