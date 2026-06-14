@echo off
echo Starting HR System Backend...
echo -----------------------------------
echo Python Version:
python --version
echo -----------------------------------
echo Starting uvicorn...
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
