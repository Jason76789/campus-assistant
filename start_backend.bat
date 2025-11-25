@echo off
cd /d "d:\python\campus-assistant"
echo Starting backend server...
python.exe -m uvicorn mcp.app:app --host 0.0.0.0 --port 8000
