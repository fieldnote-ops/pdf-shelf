#!/usr/bin/env python3
"""校验书架：catalog.yaml ↔ PDF 文件 ↔ 页数/大小/sha256 ↔ README 收录表。"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.yaml"
README = ROOT / "README.md"
BEGIN = "<!-- catalog:begin -->"
END = "<!-- catalog:end -->"
REQUIRED = ("id", "title", "series", "version", "date", "size_bytes", "sha256", "path", "status")
VALID_STATUS = {"complete", "partial", "draft"}

errors: list[str] = []
warnings: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_pages(path: Path) -> int | None:
    try:
        out = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=True
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MiB"
    return f"{size / 1024:.0f} KiB"


def main() -> int:
    if not CATALOG.is_file():
        print("错误：缺少 catalog.yaml", file=sys.stderr)
        return 1
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    if data.get("schema") != 1:
        error(f"catalog schema 应为 1，实际 {data.get('schema')!r}")
    entries = data.get("entries")
    if not isinstance(entries, list):
        print("错误：catalog.entries 必须是列表", file=sys.stderr)
        return 1

    updated = data.get("updated")
    try:
        dt.date.fromisoformat(str(updated))
    except ValueError:
        error(f"catalog.updated 不是 ISO 日期：{updated!r}")

    readme_text = README.read_text(encoding="utf-8") if README.is_file() else ""
    if BEGIN not in readme_text or END not in readme_text:
        error(f"README.md 缺少标记 {BEGIN} / {END}")

    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    total_pages = 0
    total_size = 0
    for index, entry in enumerate(entries, start=1):
        label = entry.get("title") or f"第 {index} 条"
        if not isinstance(entry, dict):
            error(f"第 {index} 条不是映射")
            continue
        missing = [key for key in REQUIRED if key not in entry]
        if missing:
            error(f"{label}：缺少字段 {', '.join(missing)}")
            continue
        entry_id = str(entry["id"])
        if entry_id in seen_ids:
            error(f"id 重复：{entry_id}")
        seen_ids.add(entry_id)
        if entry.get("status") not in VALID_STATUS:
            error(f"{label}：非法 status {entry.get('status')!r}")
        if not re.fullmatch(r"\d{4}\.\d{2}", str(entry["version"])):
            error(f"{label}：version 应形如 2026.11")

        relative = Path(str(entry["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            error(f"{label}：path 必须是仓库内相对路径：{relative}")
            continue
        if relative.as_posix() in seen_paths:
            error(f"path 重复：{relative}")
        seen_paths.add(relative.as_posix())
        if relative.as_posix() not in readme_text:
            error(f"{label}：README 收录表未包含 {relative}")

        file = ROOT / relative
        if not file.is_file():
            error(f"{label}：文件不存在 {relative}")
            continue
        size = file.stat().st_size
        if size != entry["size_bytes"]:
            error(f"{label}：大小不符，catalog {entry['size_bytes']} / 实际 {size}")
        digest = sha256_of(file)
        if digest != entry["sha256"]:
            error(f"{label}：sha256 不符，catalog {str(entry['sha256'])[:12]}… / 实际 {digest[:12]}…")

        pages = pdf_pages(file)
        if pages is None:
            warn(f"{label}：本机缺少 pdfinfo，跳过页数校验")
        elif entry.get("pages") is None:
            warn(f"{label}：catalog 未记录页数")
        elif pages != entry["pages"]:
            error(f"{label}：页数不符，catalog {entry['pages']} / 实际 {pages}")

        total_pages += int(entry.get("pages") or 0)
        total_size += int(entry["size_bytes"])
        print(f"✓ {label}  {entry.get('pages') or '?'} 页 / {human_size(size)}")

    for message in warnings:
        print(f"警告：{message}", file=sys.stderr)
    for message in errors:
        print(f"错误：{message}", file=sys.stderr)
    if errors:
        print(f"\n共 {len(errors)} 处错误。", file=sys.stderr)
        return 1
    print(f"\n通过：{len(entries)} 本 / {total_pages} 页 / {human_size(total_size)}。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
