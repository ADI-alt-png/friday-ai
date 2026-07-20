@echo off
echo Starting FRIDAY Auto-Sync in background...
start /min powershell -WindowStyle Hidden -File "D:\python exp\friday ai\auto-sync.ps1"
echo Auto-sync running! Changes will auto-push to GitHub every 2 minutes.
