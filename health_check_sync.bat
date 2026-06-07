@echo off
cd /d C:\Users\SrikanthMudaliar\AI-Cloud-Advisor
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\SrikanthMudaliar\AI-Cloud-Advisor\health_check_sync.ps1 >> health_check.log 2>&1
