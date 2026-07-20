# FRIDAY Auto-Sync: Watches for changes and auto-pushes to GitHub
# Run this in background: PowerShell -WindowStyle Hidden -File auto-sync.ps1

$repoPath = "D:\python exp\friday ai"
$logFile = "$repoPath\sync_log.txt"

function Write-Log {
    param($msg)
    $time = Get-Date -Format "HH:mm:ss"
    "$time - $msg" | Out-File -FilePath $logFile -Append
}

Write-Log "Auto-sync started"

while ($true) {
    try {
        Set-Location $repoPath
        
        # Check for changes
        $status = git status --porcelain
        if ($status) {
            Write-Log "Changes detected, committing..."
            git add -A
            git commit -m "Auto-sync update"
            git push
            Write-Log "Pushed to GitHub"
        }
    } catch {
        Write-Log "Error: $_"
    }
    
    Start-Sleep -Seconds 120  # Check every 2 minutes
}
