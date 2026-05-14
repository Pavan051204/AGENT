# Enterprise AI Multi-Agent System

This project is a multi-agent AI system designed for enterprise environments. It features multiple specialized agents, including an HR Agent and an IT Agent, capable of handling complex reasoning, tool calling, and workflow routing. 

## Key Features
- **Specialized Agents**: HR and IT agents for task automation.
- **RAG Integration**: Advanced Retrieval-Augmented Generation for document understanding.
- **Tool Calling**: Agents dynamically interact with external APIs, ticket management systems, and internal databases.
- **FastAPI Backend**: High-performance backend routing requests and exposing RESTful endpoints.

## Getting Started

We have provided one-command scripts for easy setup and execution on Windows.

### 1. Setup
To create the virtual environment and install all necessary dependencies, simply run:
```powershell
.\setup.bat
```

### 2. Run the Server
Once setup is complete, you can start the application with a single command:
```powershell
.\run.bat
```
This will automatically activate the virtual environment and start the FastAPI server with live reloading.
