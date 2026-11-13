@echo off
rem 13/11: Daily 0.2.13 4c con lo schermo sulla 3060 (riserve 1000 sulla 2080 Ti, 3000 sulla 3060)
set "S=D:\ds4_work\strata\Strata"
set "B=D:\ds4_work\strata\Strata\build-02131-4c-daily"
set "STRATA_PROMPT_ENCODER=1"
"%S%\.venv\Scripts\python.exe" "%B%\source\serve\server.py" --engine strata --config "%S%\strata-02131-4c-daily-schermo3060.json" --host 127.0.0.1 --port 8100
echo == server uscito
