#!/bin/bash
# SML 官網 (sml-site) 部署腳本 — Linux 版，取代舊 Windows deploy.ps1
#
# 安全設計（根治「內部檔誤發佈公開」的雷）：
#   只發佈「git 追蹤的、根目錄網頁檔(*.html/*.css/*.js)」＋ assets/。
#   → 未追蹤雜檔、.claude/、aws/、*.pid 等內部檔一律不會上公開網站。
#
# 用法：
#   bash /opt/sml/repo/deploy.sh              # 正式部署
#   bash /opt/sml/repo/deploy.sh --dryrun     # 只預覽會上傳什麼，不實際上傳
#   bash /opt/sml/repo/deploy.sh -m "訊息"    # 自訂 commit 訊息
set -euo pipefail
cd /opt/sml/repo

BUCKET="s3://boyplaymj-smlweb/sml-site"
CF_DIST="E1J9S5W173HSDB"
URL="https://site.supermahjongleague.com"

DRYRUN=""
MSG="deploy $(date -u +%Y-%m-%dT%H:%M:%SZ)"
while [ $# -gt 0 ]; do
  case "$1" in
    --dryrun) DRYRUN="--dryrun"; shift;;
    -m) MSG="${2:?}"; shift 2;;
    *) echo "未知參數: $1" >&2; exit 1;;
  esac
done

echo "======== 官網部署（白名單／git 追蹤檔）========"
[ -n "$DRYRUN" ] && echo "🧪 DRYRUN 模式：以下僅預覽，不會真的上傳"

# 1. 根目錄、git 追蹤的網頁檔（杜絕未追蹤雜檔與內部目錄）
mapfile -t WEBFILES < <(git ls-files -- '*.html' '*.css' '*.js' | grep -v '/' || true)
if [ ${#WEBFILES[@]} -eq 0 ]; then echo "⛔ 找不到任何追蹤的網頁檔，中止" >&2; exit 1; fi

echo "→ 將發佈這些網頁檔："; printf '   • %s\n' "${WEBFILES[@]}"

declare -A CT=( [html]="text/html; charset=utf-8" [css]="text/css; charset=utf-8" [js]="application/javascript; charset=utf-8" )
for f in "${WEBFILES[@]}"; do
  ext="${f##*.}"
  aws s3 cp ${DRYRUN} "$f" "$BUCKET/$f" \
    --content-type "${CT[$ext]:-application/octet-stream}" \
    --cache-control "max-age=300" ${DRYRUN:+--quiet} >/dev/null || true
  echo "   ↑ $f (${CT[$ext]:-octet-stream}, max-age=300)"
done

# 2. 資產目錄（長快取；--delete 讓已移除資產也撤下）
if [ -d assets ]; then
  echo "→ 同步 assets/（max-age=86400）"
  aws s3 sync ${DRYRUN} assets "$BUCKET/assets" --delete --cache-control "max-age=86400"
fi

if [ -n "$DRYRUN" ]; then echo "🧪 DRYRUN 結束（未上傳、未失效、未 push）"; exit 0; fi

# 3. CloudFront 失效
aws cloudfront create-invalidation --distribution-id "$CF_DIST" --paths "/*" >/dev/null
echo "✅ CloudFront 已建立失效 (/*)"

# 4. git 版本點（讓 origin/main 永遠 = 線上）
git add -A
git commit -q -m "$MSG" || echo "（無改動，沿用上一版本點）"
git push origin main
echo "✅ 已 push origin main：$(git log --oneline -1)"
echo "🌐 完成 → $URL"
