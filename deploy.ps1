# ============================================================
#  SML deploy  ->  https://site.supermahjongleague.com
#  S3: boyplaymj-smlweb/sml-site   CloudFront: E1J9S5W173HSDB
#  Usage:  powershell -File deploy.ps1
#  (path is taken from $PSScriptRoot to avoid non-ASCII path issues)
# ============================================================
$ErrorActionPreference = "Stop"
$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$b   = "s3://boyplaymj-smlweb/sml-site"
$src = $PSScriptRoot

Write-Host "[1/2] Sync to S3 ..." -ForegroundColor Cyan
# Assets (images/logo) get a 1-day browser cache -> cuts repeat CloudFront requests during streams
& $aws s3 sync "$src" "$b/" --exclude ".claude/*" --exclude "*.psd" --exclude "deploy.ps1" --exclude ".git/*" --exclude ".gitignore" --cache-control "public, max-age=86400"
# HTML/CSS/JS: short cache so content/code updates show quickly (CloudFront is also invalidated below)
& $aws s3 cp "$src\index.html" "$b/index.html" --content-type "text/html; charset=utf-8"        --cache-control "public, max-age=300"
& $aws s3 cp "$src\style.css"  "$b/style.css"  --content-type "text/css; charset=utf-8"          --cache-control "public, max-age=300"
& $aws s3 cp "$src\app.js"     "$b/app.js"     --content-type "application/javascript; charset=utf-8" --cache-control "public, max-age=300"

Write-Host "[2/2] Invalidate CloudFront ..." -ForegroundColor Cyan
& $aws cloudfront create-invalidation --distribution-id E1J9S5W173HSDB --paths "/*" --query "Invalidation.Status" --output text

Write-Host "DONE -> https://site.supermahjongleague.com" -ForegroundColor Green
