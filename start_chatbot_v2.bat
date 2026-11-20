@echo off
REM Double-click this file to start the VNIT chatbot, version 2 (agent v2).
REM It runs from the vnit-chatbot-v2 folder on port 8001, so it can run at the
REM same time as version 1 (start_chatbot.bat in vnit-chatbot, port 8000).
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

REM Version 2 uses the same models as version 1 (openai/gpt-oss-120b and -20b).
REM While the ablations are still running they need that allowance; to try v2
REM on a different model with its own allowance, remove "REM " from the next line.
REM set "AGENT_MODEL=qwen/qwen3.8-27b" & set "GENAI_MODEL=qwen/qwen3.8-27b"

echo Starting the chatbot server (version 2). Loading the AI models takes about 30 seconds;
echo the chat page opens in your browser as soon as it's ready.
start "" powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 90; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}; Start-Sleep 2 }; Start-Process 'http://127.0.0.1:8001/'"
"%PY%" -m uvicorn api.main:app --host 127.0.0.1 --port 8001

echo.
echo The server stopped. If you saw "address already in use", version 2 is probably
echo already running in another window - close that window and try again.
pause
