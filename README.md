# PDF 书架

[![check](https://github.com/fieldnote-ops/pdf-shelf/actions/workflows/check.yml/badge.svg)](https://github.com/fieldnote-ops/pdf-shelf/actions/workflows/check.yml)

个人整理的系统与工程 PDF：逐本收录，保留版本、校验值和缺口说明。不求多，只收自己读过、整理过、说得清来源的。

> [!IMPORTANT]
> 《从内核到智能体》第七篇「完整嵌入式系统」**尚未整合完整**：当前 24 章是阶段性快照，后续以新版 PDF 更新，不覆盖旧文件。详见 [嵌入式现状](docs/嵌入式现状.md)。

## 收录

<!-- catalog:begin -->
共 1 本，合计 1140 页，13.1 MiB。

| 系列 | 书名 | 版本 | 页数 | 大小 | 更新 | 状态 | 文件 |
|---|---|---|---|---|---|---|---|
| 从内核到智能体 | 从内核到智能体：系统原理解剖图解全集 | 2026.11 | 1140 | 13.1 MiB | 2026-11-18 | ⚠️ 部分整合 | [`从内核到智能体-系统原理解剖图解全集-2026.11.pdf`](<pdfs/从内核到智能体/从内核到智能体-系统原理解剖图解全集-2026.11.pdf>) |

状态说明：
- **从内核到智能体：系统原理解剖图解全集**：第七篇「完整嵌入式系统」尚未整合完整，详见 docs/嵌入式现状.md
<!-- catalog:end -->

每本的页数、大小、sha256 与版本都记录在 [`catalog.yaml`](catalog.yaml)；上表由 `scripts/add_pdf.py` 从 catalog 生成，不要手改。

## 怎么读

- 点表格里的书名直接下载 PDF；文件名带版本号（`YYYY.MM`），对应构建时的书内版本日期。
- 每册目录下有自己的 `README.md`，写这本书的结构、来源与已知缺口。
- 换版不覆盖旧文件：旧版归档到 GitHub Releases，仓库里只留当前版。

## 新增一本

见 [收录流程](docs/收录流程.md)。核心是一条命令：

```bash
python3 scripts/add_pdf.py --file <PDF 路径> --id <ascii-id> --series <系列> \
  --title "<书名>" --version 2026.11
```

## 校验

```bash
python3 scripts/check_repo.py
```

校验 catalog 与文件是否一一对应，页数、大小、sha256 是否一致；每次 push 时 CI 也会跑一遍。

## 许可

- `pdfs/` 下的 PDF 与正文：CC BY-NC-SA 4.0，见 [LICENSE](LICENSE)。
- `scripts/` 下的代码：MIT，见 [LICENSE-MIT](LICENSE-MIT)。

## 边界

只收录自己编写或有权发布的材料；第三方书籍（含译本）除非获得授权，不进入本仓库。
