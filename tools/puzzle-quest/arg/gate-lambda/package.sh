#!/usr/bin/env bash
# 打包 sml-puzzle-arg 閘門 Lambda（2a-3 部署前跑；零 npm 依賴，只用 node 內建 https/fs/path）
# 1) 把各 case 最新 build 的 _secret_bundle.json 同步進 bundles/（保持與網站殼一致）
# 2) 壓成 sml-puzzle-arg.zip（含 index.js / cases.json / bundles/）
set -euo pipefail
cd "$(dirname "$0")"

DIST="../dist"
mkdir -p bundles

# 依 cases.json 列出的 case，逐一從 dist/<case>/_secret_bundle.json 同步
for c in $(python3 -c "import json;print(' '.join(json.load(open('cases.json')).keys()))"); do
  src="$DIST/$c/_secret_bundle.json"
  if [ -f "$src" ]; then
    cp "$src" "bundles/$c.json"
    echo "  bundle sync: $c ($(python3 -c "import json;print(len(json.load(open('bundles/$c.json'))))") 節點)"
  else
    echo "  ⚠️  缺 $src — 先跑 build.py 產出該 case bundle" >&2
  fi
done

rm -f sml-puzzle-arg.zip
zip -q -r sml-puzzle-arg.zip index.js cases.json bundles
echo "✅ sml-puzzle-arg.zip 打包完成 ($(du -h sml-puzzle-arg.zip | cut -f1))"
echo "   部署(2a-3)：aws lambda update-function-code --function-name sml-puzzle-arg --zip-file fileb://sml-puzzle-arg.zip"
