param(
    [int]$Port = 8765,
    [string]$Key = "",
    [string]$ConfigFile = "friday_config.json"
)

# Colors
$Green = "Green"
$Cyan = "Cyan"
$Yellow = "Yellow"

Write-Host "╔══════════════════════════════════════╗" -ForegroundColor $Cyan
Write-Host "║    FRIDAY Remote Access Setup        ║" -ForegroundColor $Cyan
Write-Host "╚══════════════════════════════════════╝" -ForegroundColor $Cyan

# Read key from config if not provided
if (-not $Key) {
    $configPath = Join-Path $PSScriptRoot $ConfigFile
    if (Test-Path $configPath) {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
        $phoneKey = $config.phone_remote_key
        if ($phoneKey) { $Key = $phoneKey }
    }
}

# Check if local server is running
try {
    $req = Invoke-WebRequest -Uri "http://localhost:$Port" -TimeoutSec 3 -UseBasicParsing
    Write-Host "[OK] FRIDAY server running on port $Port" -ForegroundColor $Green
} catch {
    Write-Host "[!] FRIDAY server not detected on port $Port" -ForegroundColor $Yellow
    Write-Host "    Make sure FRIDAY is running first (start_friday.bat)" -ForegroundColor $Yellow
    exit 1
}

Write-Host ""
Write-Host "[*] Creating secure tunnel..." -ForegroundColor $Cyan

$urlParam = if ($Key) { "?key=$Key" } else { "" }

# Start cloudflared tunnel
$job = Start-Job -ScriptBlock {
    param($p, $s)
    $cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
    & $cloudflared tunnel --url "http://localhost:$p" --no-autoupdate 2>&1
} -ArgumentList $Port, $Key

Write-Host "[*] Waiting for tunnel URL..." -ForegroundColor $Yellow
Start-Sleep -Seconds 5

$outputFile = Join-Path $PSScriptRoot "friday_output\tunnel_url.txt"
$null = New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot "friday_output") -Force

# Poll job output for the URL
$publicUrl = $null
for ($i = 0; $i -lt 20; $i++) {
    $output = Receive-Job -Job $job 2>&1
    if ($output) {
        $match = [regex]::Match($output, 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com')
        if ($match.Success) {
            $publicUrl = $match.Value
            break
        }
    }
    Start-Sleep -Seconds 2
}

if (-not $publicUrl) {
    # Try to get from the job output again
    $output = Receive-Job -Job $job 2>&1
    $match = [regex]::Match($output, 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com')
    if ($match.Success) {
        $publicUrl = $match.Value
    }
}

if ($publicUrl) {
    $fullUrl = "$publicUrl/$urlParam"
    Set-Content -Path $outputFile -Value $fullUrl

    Write-Host ""
    Write-Host "╔══════════════════════════════════════╗" -ForegroundColor $Green
    Write-Host "║  REMOTE ACCESS ACTIVE                ║" -ForegroundColor $Green
    Write-Host "╚══════════════════════════════════════╝" -ForegroundColor $Green
    Write-Host ""
    Write-Host "URL:  " -NoNewline; Write-Host "$fullUrl" -ForegroundColor $Green
    Write-Host ""
    Write-Host "Phone chrome mein ye URL daalo:" -ForegroundColor $Yellow
    Write-Host $fullUrl -ForegroundColor $Cyan
    Write-Host ""
    Write-Host "[SAVED] $outputFile" -ForegroundColor $Green

    # Try to generate QR code
    try {
        python -c "import qrcode; url='$fullUrl'; qr=qrcode.make(url); qr.save('$(Join-Path $PSScriptRoot "friday_output\remote_qr.png")'); print('QR generated')" 2>$null
        Start-Process (Join-Path $PSScriptRoot "friday_output\remote_qr.png")
    } catch {
        Write-Host "[QR] Install 'pip install qrcode' for QR code" -ForegroundColor $Yellow
    }
} else {
    Write-Host "[!] Could not get tunnel URL" -ForegroundColor "Red"
    Write-Host "    Check internet connection" -ForegroundColor $Yellow
    Write-Host "    Or try: cloudflared tunnel --url http://localhost:$Port" -ForegroundColor $Yellow
}

Write-Host ""
Write-Host "Press Ctrl+C to stop remote access" -ForegroundColor $Yellow

# Keep running
$job | Wait-Job
