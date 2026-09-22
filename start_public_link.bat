@echo off
REM Double-click this file to put the VNIT chatbot on a public web address
REM (for example to open it on a phone or let examiners try it).
REM
REM It starts the chatbot (a second window opens - leave it open), then uses
REM Cloudflare's free "quick tunnel" to give it a temporary https:// link.
REM The link works only while BOTH windows are open and the laptop is awake.
REM Close both windows to take it offline. A new link is made each time.

cd /d "%~dp0"

set "CF=%USERPROFILE%\tools\cloudflared.exe"
if not exist "%CF%" (
    echo Downloading Cloudflare's tunnel tool - one time only, about 60 MB...
    if not exist "%USERPROFILE%\tools" mkdir "%USERPROFILE%\tools"
    powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe -OutFile '%CF%'"
)
if not exist "%CF%" (
    echo Download failed. Check the internet connection and try again.
    pause
    exit /b 1
)

echo Starting the chatbot in a second window...
start "VNIT chatbot server" cmd /c start_chatbot.bat

echo Waiting for the chatbot to finish loading - about 30 seconds...
powershell -NoProfile -Command "for ($i=0; $i -lt 90; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2).StatusCode -eq 200) { exit 0 } } catch {}; Start-Sleep 2 }; exit 1"
if errorlevel 1 (
    echo The chatbot did not start. Look at the other window for the error.
    pause
    exit /b 1
)

echo.
echo ==========================================================================
echo  Look below for a line ending in  .trycloudflare.com  - that is the
echo  public link. Copy it and open it on any phone or computer.
echo  Keep this window open. Close it to take the chatbot offline.
echo ==========================================================================
echo.
"%CF%" tunnel --url http://127.0.0.1:8000
pause
