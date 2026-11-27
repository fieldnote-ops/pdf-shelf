#!/usr/bin/env bash
# 从 catalog 取下载地址，断点续传并校验 sha256。
# 用法: scripts/fetch.sh <id> [输出目录]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
id="${1:-}"
outdir="${2:-.}"

if [[ -z "$id" ]]; then
  echo "用法：scripts/fetch.sh <id> [输出目录]" >&2
  echo "catalog 里可用的 id：" >&2
  python3 - "$ROOT" <<'PY' >&2
import sys, yaml
from pathlib import Path
catalog = yaml.safe_load((Path(sys.argv[1]) / "catalog.yaml").read_text(encoding="utf-8"))
for entry in catalog.get("entries", []):
    print(f"  {entry['id']}  {entry['title']}")
PY
  exit 2
fi

meta="$(python3 - "$ROOT" "$id" <<'PY'
import sys, yaml
from pathlib import Path
root, wanted = Path(sys.argv[1]), sys.argv[2]
catalog = yaml.safe_load((root / "catalog.yaml").read_text(encoding="utf-8"))
entry = next((item for item in catalog.get("entries", []) if item["id"] == wanted), None)
if entry is None:
    sys.exit(f"catalog 里没有 id：{wanted}")
print(entry["download_url"], entry["sha256"], entry["filename"], sep="\t")
PY
)"

IFS=$'\t' read -r url sha name <<< "$meta"
mkdir -p -- "$outdir"
dest="$outdir/$name"

if [[ -f "$dest" ]] && echo "$sha  $dest" | sha256sum -c --status; then
  echo "已存在且校验通过：$dest"
  exit 0
fi

encoded="$(python3 -c 'import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=":/?&="))' "$url")"

echo "来源：$url"
echo "保存：$dest"

if [[ -s "$dest" ]]; then
  echo "发现未完成文件，尝试续传…"
  if ! curl -fL --retry 10 --retry-all-errors --retry-delay 2 --connect-timeout 15 -C - -o "$dest" "$encoded"; then
    echo "续传失败，改为重新下载。" >&2
    rm -f -- "$dest"
    curl -fL --retry 10 --retry-all-errors --retry-delay 2 --connect-timeout 15 -o "$dest" "$encoded"
  fi
else
  curl -fL --retry 10 --retry-all-errors --retry-delay 2 --connect-timeout 15 -o "$dest" "$encoded"
fi

echo "$sha  $dest" | sha256sum -c -
echo "完成：$dest"
