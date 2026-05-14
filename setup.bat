@echo off
echo Setting up the Enterprise AI Multi-Agent System...
python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
echo Setup complete! You can now use run.bat to start the server.
