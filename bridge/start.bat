@echo off
REM Start pulse-bridge server on Windows

REM Load environment variables from .env if present
if exist .env (
    for /f "tokens=*" %%a in ('type .env ^| findstr /v "^#"') do set %%a
)

REM Default port
if not defined PORT set PORT=8000

echo Starting pulse-bridge on port %PORT%...
python -m uvicorn bridge.main:app --host 0.0.0.0 --port %PORT%