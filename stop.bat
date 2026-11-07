@echo off
rem Stops Kafka, Kafka UI and Spark. Data is kept (Docker volumes); start again with start.bat
cd /d "%~dp0"
docker compose down
