Write-Host "=== DEPLOY START ==="

Write-Host "Pulling latest code..."
git pull origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "Git pull failed"
    exit 1
}

Write-Host "Syncing dependencies..."
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "uv sync failed"
    exit 1
}

Write-Host "Restarting service..."
Restart-Service closedai-chatbot-api
if ($LASTEXITCODE -ne 0) {
    Write-Host "Service restart failed"
    exit 1
}

Write-Host "=== DEPLOY DONE ==="