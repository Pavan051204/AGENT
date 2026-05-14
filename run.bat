@echo off
echo Starting the Enterprise AI Multi-Agent System...
call .venv\Scripts\activate.bat
uvicorn src.main:app --reload
