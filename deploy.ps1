# ============================================================
#  SML deploy  ->  https://site.supermahjongleague.com
#  S3: boyplaymj-smlweb/sml-site   CloudFront: E1J9S5W173HSDB
#  Usage:  powershell -File deploy.ps1 [-msg "commit message"]
#  (path is taken from $PSScriptRoot to avoid non-ASCII path issues)
#  Steps: 1) sync to S3  2) invalidate CloudFront  3) git commit + push
# ============================================================
param([string]$msg)   # optional commit message; defaults to a timestamp
$ErrorActionPreference = "Stop"
$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$b   = "s3://boyplaymj-smlweb/sml-site"
$src = $PSScriptRoot

Write-Host "[1/3] Sync to S3 ..." -ForegroundColor Cyan
# Assets (images/logo) get a 1-day browser cache -> cuts repeat CloudFront requests during streams
& $aws s3 sync "$src" "$b/" --exclude ".claude/*" --exclude "*.psd" --exclude "deploy.ps1" --exclude ".git/*" --exclude ".gitignore" --cache-control "public, max-age=86400"
# HTML/CSS/JS: short cache so content/code updates show quickly (CloudFront is also invalidated below)
& $aws s3 cp "$src\index.html" "$b/index.html" --content-type "text/html; charset=utf-8"        --cache-control "public, max-age=300"
& $aws s3 cp "$src\style.css"  "$b/style.css"  --content-type "text/css; charset=utf-8"          --cache-control "public, max-age=300"
& $aws s3 cp "$src\app.js"     "$b/app.js"     --content-type "application/javascript; charset=utf-8" --cache-control "public, max-age=300"

Write-Host "[2/3] Invalidate CloudFront ..." -ForegroundColor Cyan
& $aws cloudfront create-invalidation --distribution-id E1J9S5W173HSDB --paths "/*" --query "Invalidation.Status" --output text

Write-Host "[3/3] Git commit & push ..." -ForegroundColor Cyan
Push-Location $src
try {
  git add -A
  if (git status --porcelain) {
    if (-not $msg) { $msg = "deploy: " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
    git commit -q -m $msg
    Write-Host "  committed: $msg" -ForegroundColor DarkGray
  } else {
    Write-Host "  no file changes to commit" -ForegroundColor DarkGray
  }
  git push -q origin main
  if ($LASTEXITCODE -eq 0) { Write-Host "  pushed -> origin/main" -ForegroundColor DarkGray }
  else { Write-Host "  WARNING: git push failed (exit $LASTEXITCODE) - site is live, but version not pushed" -ForegroundColor Yellow }
} finally {
  Pop-Location
}

Write-Host "DONE -> https://site.supermahjongleague.com  (+ pushed to GitHub)" -ForegroundColor Green
