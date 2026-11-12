@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

if not exist "%~dp0.venv-build\Scripts\python.exe" (
  echo Creating clean build environment...
  python -m venv "%~dp0.venv-build"
  if errorlevel 1 goto :error
)

set "BUILD_PY=%~dp0.venv-build\Scripts\python.exe"
"%BUILD_PY%" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :error
"%BUILD_PY%" -m PyInstaller --clean --noconfirm lexiread.spec
if errorlevel 1 goto :error

if exist "%~dp0runtime\tesseract\tesseract.exe" (
  echo Bundling Tesseract English OCR runtime...
  if not exist "%~dp0dist\runtime" mkdir "%~dp0dist\runtime"
  xcopy /E /I /Y "%~dp0runtime\tesseract" "%~dp0dist\runtime\tesseract" >nul
)

echo.
echo  Build complete: dist\LexiRead.exe
echo  Windows may show a SmartScreen warning because this public-source build is not code-signed.
echo.
pause
exit /b 0

:error
echo.
echo  Build failed. Check the output above.
pause
exit /b 1
