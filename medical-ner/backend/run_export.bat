@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python scripts/export_labeled_data.py %*
