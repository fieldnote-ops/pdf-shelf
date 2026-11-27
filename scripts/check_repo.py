#!/usr/bin/env python3
"""离线校验书架：catalog.yaml ↔ README 表格 ↔ SHA256SUMS。

不下载 PDF、不访问网络。只确认元数据自洽、下载地址指向本仓库的 Release 资产。
PDF 是否真的可下载，由发布后手动跑一次 scripts/fetch.sh 验证。
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.yaml"
README = ROOT / "README.md"
SUMS = ROOT / "SHA256SUMS"
BEGIN = "<!-- catalog:begin -->"
END = "<!-- catalog:end -->"
URL_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/releases/download/([^/]+)/(.+)$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERSION_RE = re.compile(r"^\d{4}\.\d{2}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+\.pdf$")
REQUIRED = (
    "id",
    "title",
    "series",
    "version",
    "tag",
    "date",
    "pages",
    "size_bytes",
    "sha256",
    "filename",
    "download_url",
    "status",
)
VALID_STATUS = {"complete", "partial", "draft"}

errors: list[str] = []
warnings: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


def warn(msg: str) -> None:
    warnings.append(msg)


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MiB"
    return f"{size / 1024:.0f} KiB"


def parse_sums(text: str) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2:
            error(f"SHA256SUMS 第 {number} 行格式不对：{line!r}")
            continue
        digest, name = parts
        if not HEX64.fullmatch(digest):
            error(f"SHA256SUMS 第 {number} 行哈希非法：{digest!r}")
        pairs.add((digest, name))
    return pairs


def main() -> int:
    if not CATALOG.is_file():
        print("错误：缺少 catalog.yaml", file=sys.stderr)
        return 1
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    if data.get("schema") != 2:
        error(f"catalog schema 应为 2，实际 {data.get('schema')!r}")
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

    if not SUMS.is_file():
        error("缺少 SHA256SUMS")
        sums: set[tuple[str, str]] = set()
    else:
        sums = parse_sums(SUMS.read_text(encoding="utf-8"))

    catalog_pairs: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    repos: set[str] = set()

    for index, entry in enumerate(entries, start=1):
        label = entry.get("title") or f"第 {index} 条"
        if not isinstance(entry, dict):
            error(f"第 {index} 条不是映射")
            continue
        missing = [key for key in REQUIRED if key not in entry]
        if missing:
            error(f"{label}：缺少字段 {', '.join(missing)}")
            continue

        if not ID_RE.fullmatch(str(entry["id"])):
            error(f"{label}：id 非法 {entry['id']!r}")
        if str(entry["id"]) in seen_ids:
            error(f"id 重复：{entry['id']}")
        seen_ids.add(str(entry["id"]))

        if entry.get("status") not in VALID_STATUS:
            error(f"{label}：非法 status {entry.get('status')!r}")
        if not VERSION_RE.fullmatch(str(entry["version"])):
            error(f"{label}：version 应形如 2026.11")
        if str(entry["tag"]) != f"v{entry['version']}":
            error(f"{label}：tag 应等于 v{entry['version']}，实际 {entry['tag']!r}")
        try:
            dt.date.fromisoformat(str(entry["date"]))
        except ValueError:
            error(f"{label}：date 不是 ISO 日期：{entry['date']!r}")

        if not isinstance(entry["pages"], int) or entry["pages"] <= 0:
            error(f"{label}：pages 必须是正整数")
        if not isinstance(entry["size_bytes"], int) or entry["size_bytes"] <= 0:
            error(f"{label}：size_bytes 必须是正整数")
        if not HEX64.fullmatch(str(entry["sha256"])):
            error(f"{label}：sha256 必须是 64 位小写十六进制")

        filename = str(entry["filename"])
        if "/" in filename or not FILENAME_RE.fullmatch(filename):
            error(f"{label}：filename 必须是 ASCII 的单个 PDF 文件名")
        if filename in seen_names:
            error(f"filename 重复：{filename}")
        seen_names.add(filename)

        url = str(entry["download_url"])
        matched = URL_RE.fullmatch(url)
        if not matched:
            error(f"{label}：download_url 不是 GitHub Release 资产地址：{url}")
        else:
            repos.add(f"{matched.group(1)}/{matched.group(2)}")
            if matched.group(3) != entry["tag"]:
                error(f"{label}：地址里的 tag 与 tag 字段不一致")
            if unquote(matched.group(4)) != filename:
                error(f"{label}：地址里的文件名与 filename 不一致")
        if url in seen_urls:
            error(f"download_url 重复：{url}")
        seen_urls.add(url)
        if url not in readme_text:
            error(f"{label}：README 里没有下载地址")

        mirrors = entry.get("mirrors", [])
        if not isinstance(mirrors, list):
            error(f"{label}：mirrors 必须是列表")
        else:
            for mirror in mirrors:
                if not str(mirror).startswith("https://"):
                    error(f"{label}：mirror 必须是 https 地址：{mirror}")

        catalog_pairs.add((str(entry["sha256"]), filename))
        print(f"✓ {label}  {entry['pages']} 页 / {human_size(int(entry['size_bytes']))}  →  {entry['tag']}")

    if len(repos) > 1:
        error(f"同一 catalog 里出现了多个仓库：{', '.join(sorted(repos))}")
    if catalog_pairs != sums:
        for pair in sorted(catalog_pairs - sums):
            error(f"SHA256SUMS 缺少：{pair[1]}")
        for pair in sorted(sums - catalog_pairs):
            warn(f"SHA256SUMS 多出：{pair[1]}")

    for message in warnings:
        print(f"警告：{message}", file=sys.stderr)
    for message in errors:
        print(f"错误：{message}", file=sys.stderr)
    if errors:
        print(f"\n共 {len(errors)} 处错误。", file=sys.stderr)
        return 1
    print(f"\n通过：{len(entries)} 本（离线校验，不访问网络）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
