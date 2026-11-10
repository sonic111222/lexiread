@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo  没有找到 Python。请先安装 Python 3.10 或更高版本。
  echo  https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

python -c "import flask, requests, PIL" >nul 2>nul
if errorlevel 1 (
  echo.
  echo  首次运行，正在安装依赖...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo  依赖安装失败。请检查网络，或在命令行运行：
    echo  python -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
)

python app.py
if errorlevel 1 pause
