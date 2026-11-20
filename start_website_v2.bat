@echo off
REM Double-click this file to start the VNIT website demo with chatbot version 2
REM (agent v2) in the corner of every page. It runs from the vnit-chatbot-v2 folder
REM on port 8001, next to version 1 on port 8000.
REM The website's widget with streaming comes from vnit-website's branch agent-v2;
REM on its master branch the old widget is shown, which still works with version 2.
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

REM To try v2 on a model with its own allowance while the ablations run,
REM remove "REM " from the next line (see start_chatbot_v2.bat).
REM set "AGENT_MODEL=qwen/qwen3.8-27b" & set "GENAI_MODEL=qwen/qwen3.8-27b"

echo Starting the chatbot server (version 2). Loading the AI models takes about 30 seconds;
echo the website opens in your browser as soon as it's ready.
start "" powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 90; $i++) { try { if ((Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8001/health -TimeoutSec 2).StatusCode -eq 200) { break } } catch {}; Start-Sleep 2 }; Start-Process 'http://127.0.0.1:8001/site/'"
"%PY%" -m uvicorn api.main:app --host 127.0.0.1 --port 8001

echo.
echo The server stopped. If you saw "address already in use", version 2 is probably
echo already running in another window - close that window and try again.
pause
