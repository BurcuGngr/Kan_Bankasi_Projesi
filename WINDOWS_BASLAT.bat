@echo off
setlocal
cd /d "%~dp0"
title Kan Bankasi - Ilk Kurulum

echo [1/4] Python kontrol ediliyor...
where py >nul 2>nul
if errorlevel 1 (
    where python >nul 2>nul
    if errorlevel 1 (
        echo.
        echo HATA: Python bulunamadi.
        echo https://www.python.org/downloads/ adresinden Python kurun.
        echo Kurulumda "Add Python to PATH" secenegini isaretleyin.
        pause
        exit /b 1
    )
    set "PYTHON_KOMUTU=python"
) else (
    set "PYTHON_KOMUTU=py"
)

if not exist ".venv\Scripts\python.exe" (
    echo [2/4] Python sanal ortami olusturuluyor...
    %PYTHON_KOMUTU% -m venv .venv
    if errorlevel 1 goto :hata
)

echo [2/4] Python kutuphaneleri kontrol ediliyor...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :hata

if not exist "data\kan_bankasi.db" (
    echo [3/4] Ornek veritabani olusturuluyor...
    ".venv\Scripts\python.exe" veriler.py
    if errorlevel 1 goto :hata
)

where npm >nul 2>nul
if errorlevel 1 (
    echo.
    echo HATA: Node.js ve npm bulunamadi.
    echo https://nodejs.org/ adresinden LTS surumunu kurun.
    pause
    exit /b 1
)

if not exist "frontend\node_modules" (
    echo [3/4] Arayuz kutuphaneleri kuruluyor...
    pushd frontend
    call npm install
    if errorlevel 1 (
        popd
        goto :hata
    )
    popd
)

echo [4/4] API ve yonetici paneli baslatiliyor...
start "Kan Bankasi API" cmd /k "cd /d ""%~dp0"" && "".venv\Scripts\python.exe"" app.py"
start "Kan Bankasi Paneli" cmd /k "cd /d ""%~dp0frontend"" && npm run dev"

timeout /t 5 /nobreak >nul
start "" "http://localhost:5173"
exit /b 0

:hata
echo.
echo Kurulum sirasinda hata olustu. Bu pencerenin ekran goruntusunu alin.
pause
exit /b 1
