#!/usr/bin/env python3
"""登记一本 PDF：读取元数据，写入 catalog、README 表格与 SHA256SUMS。

PDF 本身不进 git，也不由本脚本保存；它由 GitHub Release 托管。
校验脚本只做离线一致性检查，不访问网络。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.yaml"
README = ROOT / "README.md"
SUMS = ROOT / "SHA256SUMS"
BEGIN = "<!-- catalog:begin -->"
END = "<!-- catalog:end -->"
STATUS_LABELS = {
    "complete": "✅ 完整",
    "partial": "⚠️ 部分整合",
    "draft": "🚧 草稿",
}


def fail(msg: str) -> None:
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(1)


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pdf_meta(path: Path) -> tuple[int | None, str | None]:
    """返回 (页数, 创建日期 ISO)。依赖 poppler 的 pdfinfo，缺失时返回 (None, None)。"""
    try:
        out = subprocess.run(
            ["pdfinfo", str(path)], capture_output=True, text=True, check=True
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None, None

    pages = None
    date = None
    for line in out.splitlines():
        if line.startswith("Pages:"):
            try:
                pages = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("CreationDate:"):
            matched = re.search(
                r"([A-Z][a-z]{2})\s+([A-Z][a-z]{2})\s+(\d{1,2})\s+"
                r"(\d{2}):(\d{2}):(\d{2})\s+(\d{4})",
                line,
            )
            if matched:
                _, month, day, _hh, _mm, _ss, year = matched.groups()
                try:
                    date = dt.datetime.strptime(
                        f"{day} {month} {year}", "%d %b %Y"
                    ).date().isoformat()
                except ValueError:
                    pass
    return pages, date


def safe_name(text: str) -> str:
    """去掉路径分隔符、Windows 非法字符与空白，保留中文。"""
    text = re.sub(r'[\\/:*?"<>|]', "-", text)
    return re.sub(r"\s+", "-", text).strip("-")


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MiB"
    return f"{size / 1024:.0f} KiB"


def cell(text: object) -> str:
    return str(text).replace("|", "\\|")


def repo_slug(explicit: str | None) -> str:
    if explicit:
        slug = explicit
    else:
        try:
            remote = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            fail("读不到 git remote.origin.url，请用 --repo owner/repo 指定")
        matched = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", remote)
        if not matched:
            fail(f"无法从 remote 解析仓库：{remote}")
        slug = f"{matched.group(1)}/{matched.group(2)}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        fail(f"仓库名应形如 owner/repo：{slug}")
    return slug


def load_catalog() -> dict:
    if not CATALOG.exists():
        return {"schema": 2, "updated": dt.date.today().isoformat(), "entries": []}
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    data.setdefault("schema", 2)
    data.setdefault("entries", [])
    return data


def save_catalog(data: dict) -> None:
    data["schema"] = 2
    data["updated"] = dt.date.today().isoformat()
    CATALOG.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def write_sums(entries: list[dict]) -> None:
    lines = [
        f"{entry['sha256']}  {entry['filename']}"
        for entry in sorted(entries, key=lambda item: item["filename"])
    ]
    SUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_table(entries: list[dict]) -> str:
    total_pages = sum(int(entry.get("pages") or 0) for entry in entries)
    total_size = sum(int(entry["size_bytes"]) for entry in entries)
    lines = [
        f"共 {len(entries)} 本，合计 {total_pages} 页，{human_size(total_size)}。",
        "",
        "| 系列 | 书名 | 版本 | 页数 | 大小 | 状态 | 下载 |",
        "|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {series} | {title} | {version} | {pages} | {size} | {status} | {link} |".format(
                series=cell(entry.get("series", "")),
                title=cell(entry["title"]),
                version=cell(entry.get("version", "")),
                pages=entry.get("pages") or "—",
                size=human_size(int(entry["size_bytes"])),
                status=STATUS_LABELS.get(entry.get("status", "complete"), entry.get("status", "")),
                link=f"[PDF](<{entry['download_url']}>)",
            )
        )

    notes = [entry for entry in entries if entry.get("status_note")]
    if notes:
        lines += ["", "状态说明："]
        for entry in notes:
            lines.append(f"- **{entry['title']}**：{entry['status_note']}")
    return "\n".join(lines)


def update_readme(table: str) -> None:
    text = README.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        fail(f"README.md 缺少标记 {BEGIN} / {END}")
    pattern = re.escape(BEGIN) + r".*?" + re.escape(END)
    replacement = f"{BEGIN}\n{table}\n{END}"
    README.write_text(re.sub(pattern, lambda _: replacement, text, flags=re.S), encoding="utf-8")


def upload_asset(tag: str, source: Path, filename: str) -> None:
    """把源文件以目标文件名上传到已存在的 Release。"""
    with tempfile.TemporaryDirectory(prefix="pdf-shelf-upload-") as tmp:
        named = Path(tmp) / filename
        shutil.copy2(source, named)
        result = subprocess.run(
            ["gh", "release", "upload", tag, str(named), "--clobber"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        fail(f"上传失败（Release {tag} 是否已存在？）：{result.stderr.strip()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="登记一本 PDF 到书架（PDF 由 Release 托管）")
    parser.add_argument("--file", required=True, type=Path, help="本地 PDF，用于计算页数/大小/哈希")
    parser.add_argument("--id", required=True, help="稳定的 ASCII 标识，如 system-atlas")
    parser.add_argument("--series", required=True, help="系列目录名，如 从内核到智能体")
    parser.add_argument("--title", required=True, help="书名")
    parser.add_argument("--version", required=True, help="版本号，形如 2026.11")
    parser.add_argument("--tag", help="Release tag，默认 v<version>")
    parser.add_argument("--filename", help="Release 资产文件名，默认 <书名>-<版本>.pdf")
    parser.add_argument("--status", default="complete", choices=sorted(STATUS_LABELS))
    parser.add_argument("--status-note", default="", help="状态说明，写在 README 表下方")
    parser.add_argument("--source", default="", help="构建来源，如 Typst 0.15.1 / docs 仓库")
    parser.add_argument("--mirror", action="append", default=[], help="备用下载地址，可重复")
    parser.add_argument("--repo", help="owner/repo，默认从 git remote 推断")
    parser.add_argument("--replace", action="store_true", help="同 id 换版：替换旧条目")
    parser.add_argument("--upload", action="store_true", help="登记后把 PDF 传到已存在的 Release")
    parser.add_argument("--dry-run", action="store_true", help="只打印条目，不写文件")
    args = parser.parse_args()

    source = args.file.expanduser().resolve()
    if not source.is_file():
        fail(f"源文件不存在：{source}")
    if source.suffix.lower() != ".pdf":
        fail(f"不是 PDF：{source}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", args.id):
        fail("--id 只能用小写字母、数字和连字符")
    if not re.fullmatch(r"\d{4}\.\d{2}", args.version):
        fail("--version 形如 2026.11")
    tag = args.tag or f"v{args.version}"
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", tag):
        fail(f"tag 非法：{tag}")

    data = load_catalog()
    entries = data["entries"]
    existing = next((entry for entry in entries if entry.get("id") == args.id), None)
    if existing and not args.replace:
        fail(f"catalog 已存在 id：{args.id}（换版请加 --replace）")

    title = args.title.strip()
    filename = safe_name(args.filename or f"{title}-{args.version}.pdf")
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    size = source.stat().st_size
    if size > 2 * 1024 * 1024 * 1024:
        fail(f"文件 {human_size(size)} 超过 GitHub Release 单资产 2 GB 上限")
    if size > 100 * 1024 * 1024:
        print(f"注意：{human_size(size)} 偏大，下载体验可能较差。", file=sys.stderr)

    pages, date = pdf_meta(source)
    if pages is None:
        print("警告：读不到页数（缺 pdfinfo），catalog 将记为空。", file=sys.stderr)

    slug = repo_slug(args.repo)
    download_url = f"https://github.com/{slug}/releases/download/{tag}/{filename}"
    mirrors = [item.strip() for item in args.mirror if item.strip()]
    for mirror in mirrors:
        if not mirror.startswith("https://"):
            fail(f"mirror 必须是 https 地址：{mirror}")

    entry = {
        "id": args.id,
        "title": title,
        "series": args.series,
        "version": args.version,
        "tag": tag,
        "date": date or dt.date.today().isoformat(),
        "pages": pages,
        "size_bytes": size,
        "sha256": sha256_of(source),
        "filename": filename,
        "download_url": download_url,
        "mirrors": mirrors,
        "status": args.status,
        "status_note": args.status_note,
        "source": args.source,
        "added": dt.date.today().isoformat(),
    }
    if not entry["status_note"]:
        entry.pop("status_note")

    if args.dry_run:
        print(yaml.safe_dump(entry, allow_unicode=True, sort_keys=False).rstrip())
        print(f"[dry-run] 将登记 {filename}（{download_url}）")
        return

    if args.upload:
        upload_asset(tag, source, filename)

    if existing:
        entries.remove(existing)
    entries.append(entry)
    save_catalog(data)
    update_readme(render_table(entries))
    write_sums(entries)

    print(f"{'已更新' if existing else '已登记'}：{entry['title']}")
    print(f"  {entry['pages'] or '?'} 页 / {human_size(size)} / sha256 {entry['sha256'][:12]}…")
    print(f"  下载：{download_url}")


if __name__ == "__main__":
    main()
