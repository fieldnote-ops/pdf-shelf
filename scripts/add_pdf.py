#!/usr/bin/env python3
"""把一本 PDF 收录进书架。

复制文件到 pdfs/<系列>/，读取页数/大小/哈希，写入 catalog.yaml，
并重新生成 README 的收录表。catalog 是唯一事实来源，README 不要手改。
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog.yaml"
README = ROOT / "README.md"
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
    """去掉路径分隔符与 Windows 非法字符，保留中文。"""
    return re.sub(r'[\\/:*?"<>|]', "-", text).strip()


def human_size(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / 1024 / 1024:.1f} MiB"
    return f"{size / 1024:.0f} KiB"


def cell(text: object) -> str:
    return str(text).replace("|", "\\|")


def load_catalog() -> dict:
    if not CATALOG.exists():
        return {"schema": 1, "updated": dt.date.today().isoformat(), "entries": []}
    data = yaml.safe_load(CATALOG.read_text(encoding="utf-8")) or {}
    data.setdefault("schema", 1)
    data.setdefault("entries", [])
    return data


def save_catalog(data: dict) -> None:
    data["updated"] = dt.date.today().isoformat()
    CATALOG.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )


def render_table(entries: list[dict]) -> str:
    total_pages = sum(e.get("pages") or 0 for e in entries)
    total_size = sum(int(e["size_bytes"]) for e in entries)
    lines = [
        f"共 {len(entries)} 本，合计 {total_pages} 页，{human_size(total_size)}。",
        "",
        "| 系列 | 书名 | 版本 | 页数 | 大小 | 更新 | 状态 | 文件 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| {series} | {title} | {version} | {pages} | {size} | {date} | {status} | {link} |".format(
                series=cell(entry.get("series", "")),
                title=cell(entry["title"]),
                version=cell(entry.get("version", "")),
                pages=entry.get("pages") or "—",
                size=human_size(int(entry["size_bytes"])),
                date=cell(entry.get("date", "")),
                status=STATUS_LABELS.get(entry.get("status", "complete"), entry.get("status", "")),
                link=f"[`{Path(entry['path']).name}`](<{entry['path']}>)",
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="收录一本 PDF，并更新 catalog.yaml 与 README.md"
    )
    parser.add_argument("--file", required=True, type=Path, help="源 PDF 路径")
    parser.add_argument("--id", required=True, help="稳定的 ASCII 标识，如 from-kernel-to-agent")
    parser.add_argument("--series", required=True, help="系列目录名，如 从内核到智能体")
    parser.add_argument("--title", required=True, help="书名")
    parser.add_argument("--version", required=True, help="版本号，形如 2026.11")
    parser.add_argument("--filename", help="仓库内文件名，默认 <书名>-<版本>.pdf")
    parser.add_argument(
        "--status", default="complete", choices=sorted(STATUS_LABELS), help="整合状态"
    )
    parser.add_argument("--status-note", default="", help="状态说明，写在 README 表下方")
    parser.add_argument("--source", default="", help="构建来源，如 Typst 0.15.1 / docs 仓库")
    parser.add_argument("--dry-run", action="store_true", help="只校验并打印，不写文件")
    parser.add_argument("--replace", action="store_true", help="同 id 换版：覆盖旧条目与旧文件")
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

    data = load_catalog()
    entries = data["entries"]
    existing = next((entry for entry in entries if entry.get("id") == args.id), None)
    if existing and not args.replace:
        fail(f"catalog 已存在 id：{args.id}（换版请加 --replace，见 docs/收录流程.md）")

    title = args.title.strip()
    filename = safe_name(args.filename or f"{title}-{args.version}.pdf")
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    relative = Path("pdfs") / safe_name(args.series) / filename
    target = ROOT / relative
    digest = sha256_of(source)
    same_path = bool(existing and existing.get("path") == relative.as_posix())
    if target.exists() and sha256_of(target) != digest and not same_path:
        fail(f"目标已存在且内容不同：{relative}")

    size = source.stat().st_size
    if size > 100 * 1024 * 1024:
        fail(f"文件 {human_size(size)} 超过 GitHub 100 MB 单文件上限")
    if size > 50 * 1024 * 1024:
        print(f"注意：{human_size(size)} 偏大，建议改用 GitHub Releases 托管。", file=sys.stderr)

    pages, date = pdf_meta(source)
    entry = {
        "id": args.id,
        "title": title,
        "series": args.series,
        "version": args.version,
        "date": date or dt.date.today().isoformat(),
        "pages": pages,
        "size_bytes": size,
        "sha256": digest,
        "path": relative.as_posix(),
        "status": args.status,
        "status_note": args.status_note,
        "source": args.source,
        "added": dt.date.today().isoformat(),
    }
    if not entry["status_note"]:
        entry.pop("status_note")

    if args.dry_run:
        print(yaml.safe_dump(entry, allow_unicode=True, sort_keys=False).rstrip())
        action = "替换" if existing else "新增"
        print(f"[dry-run] 将{action} {relative}，并更新 catalog/README")
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or sha256_of(target) != digest:
        shutil.copy2(source, target)
    if existing:
        old_file = ROOT / str(existing["path"])
        if old_file != target and old_file.exists():
            old_file.unlink()
        entries.remove(existing)
    entries.append(entry)
    save_catalog(data)
    update_readme(render_table(entries))

    print(f"{'已更新' if existing else '已收录'}：{relative}")
    print(
        f"  {entry['pages'] or '?'} 页 / {human_size(size)} / "
        f"sha256 {entry['sha256'][:12]}…"
    )


if __name__ == "__main__":
    main()
