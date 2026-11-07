@echo off
rem Starts the attendance app; the app starts Docker, Kafka and Spark by itself.
rem Extra arguments are passed on, e.g. start.bat -Port 8502
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
