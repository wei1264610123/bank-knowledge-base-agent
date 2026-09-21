@echo off
echo ========================================
echo   Installing dependencies step by step
echo ========================================
echo.

cd /d "%~dp0backend"

echo [1/5] Upgrading pip...
python -m pip install --upgrade pip

echo [2/5] Installing numpy (pre-compiled)...
pip install numpy==1.26.4 --only-binary=:all:

echo [3/5] Installing other base packages...
pip install pydantic pydantic-settings python-dotenv aiofiles httpx

echo [4/5] Installing FastAPI and database packages...
pip install fastapi uvicorn python-multipart sqlalchemy aiosqlite alembic python-jose passlib

echo [5/5] Installing LangChain and other packages...
pip install langchain langchain-openai langchain-community pymilvus pypdf docx2txt

echo.
echo ========================================
echo   Installation complete!
echo ========================================
pause
