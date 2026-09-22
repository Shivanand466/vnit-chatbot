@echo off
REM Double-click this file to start the VNIT chatbot.
REM It starts the answering server, then opens the chat page in your browser.
REM Keep this black window open while using the chatbot; close it to stop.

cd /d "%~dp0"

set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"

set "KEYFILE=%USERPROFILE%\groq-key.txt"
if exist "%KEYFILE%" (
    set /p GENAI_API_KEY=<"%KEYFILE%"
    echo Groq key loaded from %KEYFILE%
) else (
    echo.
    echo  NOTE: no Groq key file found at %KEYFILE%
    echo  The chatbot will still work, but in "extractive" mode:
    echo  it shows matching passages instead of writing full answers.
    echo  To fix: save your Groq API key alone on one line in that file.
    echo.
)

echo Starting the chatbot server. Loading the AI models takes about 30 seconds;
echo the chat page opens in your browser as soon as it's ready.
start "" powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 90; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/health -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}; Start-Sleep 2 }; Start-Process 'http://127.0.0.1:8000/'"
"%PY%" -m uvicorn api.main:app --host 127.0.0.1 --port 8000

echo.
echo The server stopped. If you saw "address already in use", the chatbot is probably
echo already running in another window - close that window and try again.
pause
