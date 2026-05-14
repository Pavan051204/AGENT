# Enterprise AI Multi-Agent System

This project is a multi-agent AI system designed for enterprise environments. It features multiple specialized agents, including an HR Agent and an IT Agent, capable of handling complex reasoning, tool calling, and workflow routing. 

## Key Features
- **Specialized Agents**: HR and IT agents for task automation.
- **RAG Integration**: Advanced Retrieval-Augmented Generation for document understanding.
- **Tool Calling**: Agents dynamically interact with external APIs, ticket management systems, and internal databases.
- **FastAPI Backend**: High-performance backend routing requests and exposing RESTful endpoints.

## Getting Started
To run the server locally:
```bash
uvicorn src.main:app --reload
```
