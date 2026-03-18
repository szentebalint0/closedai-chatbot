Write-Host "=== GIT COMMIT & PUSH ===" 

$commitMessage = Read-Host "`nEnter commit message"

if ([string]::IsNullOrWhiteSpace($commitMessage)) {
    Write-Host "Commit message cannot be empty"
    exit 1
}

$confirm = Read-Host "Proceed with commit & push? (y/n)"
if ($confirm -ne "y") {
    Write-Host "Aborted"
    exit 0
}

Write-Host "`nAdding changes..." 
git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "git add failed" 
    exit 1
}

Write-Host "Committing..."
git commit -m "$commitMessage"
if ($LASTEXITCODE -ne 0) {
    Write-Host "git commit failed (no changes?)"
    exit 1
}

Write-Host "Pushing to origin main..." 
git push origin main
if ($LASTEXITCODE -ne 0) {
    Write-Host "git push failed" 
    exit 1
}

Write-Host "DONE"