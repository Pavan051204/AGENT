#!/usr/bin/env python3
"""
Quick test script to verify the RAG system setup
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required modules can be imported"""
    print("✓ Testing imports...")
    try:
        from src.settings import get_config
        from src.tools.vector_store import VectorStore
        from src.tools.pdf_ingest import ingest_pdfs
        from src.agents.retrieval_agent import RAGAgent
        print("  ✓ All imports successful")
        return True
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False


def test_config():
    """Test that configuration loads correctly"""
    print("✓ Testing configuration...")
    try:
        from src.settings import get_config
        config = get_config()
        
        assert config.gemini_api_key, "GEMINI_API_KEY not set"
        assert config.gemini_model, "GEMINI_MODEL not set"
        assert config.pdf_docs_path, "PDF_DOCS_PATH not set"
        
        print(f"  ✓ Gemini API Key: {config.gemini_api_key[:20]}...")
        print(f"  ✓ Model: {config.gemini_model}")
        print(f"  ✓ PDF Path: {config.pdf_docs_path}")
        return True
    except Exception as e:
        print(f"  ✗ Config test failed: {e}")
        return False


def test_pdfs():
    """Test that PDFs exist in docs folder"""
    print("✓ Testing PDF files...")
    try:
        docs_path = Path("./docs")
        pdfs = list(docs_path.glob("*.pdf"))
        
        if not pdfs:
            print("  ✗ No PDFs found in docs/ folder")
            return False
        
        print(f"  ✓ Found {len(pdfs)} PDF files:")
        for pdf in sorted(pdfs):
            print(f"    - {pdf.name}")
        return True
    except Exception as e:
        print(f"  ✗ PDF test failed: {e}")
        return False


def test_rag_agent():
    """Test that RAG agent initializes"""
    print("✓ Testing RAG Agent...")
    try:
        from src.agents.retrieval_agent import RAGAgent
        agent = RAGAgent()
        print(f"  ✓ RAG Agent initialized")
        print(f"  ✓ Model: {agent.model}")
        return True
    except Exception as e:
        print(f"  ✗ RAG Agent test failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*50)
    print("  RAG System Verification")
    print("="*50 + "\n")
    
    tests = [
        test_imports,
        test_config,
        test_pdfs,
        test_rag_agent,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test error: {e}")
            results.append(False)
        print()
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*50)
    print(f"Results: {passed}/{total} tests passed")
    print("="*50)
    
    if passed == total:
        print("\n✓ System is ready to run!")
        print("\nNext steps:")
        print("  1. uvicorn src.main:app --reload")
        print("  2. Open http://localhost:8000")
        print("  3. Ask a policy question!")
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
