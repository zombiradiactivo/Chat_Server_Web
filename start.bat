@echo off
echo ========================================
echo    Chat Server Web - Iniciar Servidor
echo ========================================
echo.
echo Iniciando el servidor en http://localhost:8000
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause