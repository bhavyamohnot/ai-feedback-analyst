# Starts everything the two n8n workflows need, then opens n8n at http://localhost:5678
#   powershell -ExecutionPolicy Bypass -File n8n\start_n8n.ps1
$root = Split-Path $PSScriptRoot -Parent

# 1. The review API (search + stats tools for the AI agent). Skip if it is already running.
$up = Test-NetConnection 127.0.0.1 -Port 8765 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $up) {
    Start-Process python -ArgumentList "-X", "utf8", "`"$root\src\api.py`"" -WorkingDirectory $root -WindowStyle Minimized
    Write-Host "review API starting on http://127.0.0.1:8765"
}

# 2. n8n settings (environment variables are how n8n is configured)
$env:NODES_EXCLUDE = "[]"                                       # n8n 2.x hides Execute Command by default; the digest needs it
$env:N8N_RESTRICT_FILE_ACCESS_TO = "$root\data\digest"          # file nodes may only touch the digest folder
$env:GENERIC_TIMEZONE = "Asia/Kolkata"                          # "Monday 9am" means Indian time
$env:N8N_DIAGNOSTICS_ENABLED = "false"                          # no telemetry
$env:N8N_LISTEN_ADDRESS = "127.0.0.1"                           # only this laptop can open n8n (not the Wi-Fi network)

# 3. n8n needs Node 24 (Node 26 is too new for one of its parts), so it uses a portable Node 24 in tools\
$tools = "$env:USERPROFILE\tools"
$env:Path = "$tools\node-v24.22.3-win-x64;$env:Path"
& "$tools\n8n\node_modules\.bin\n8n.cmd" start
