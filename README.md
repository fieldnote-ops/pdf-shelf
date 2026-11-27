# PDF 书架

[![check](https://github.com/fieldnote-ops/pdf-shelf/actions/workflows/check.yml/badge.svg)](https://github.com/fieldnote-ops/pdf-shelf/actions/workflows/check.yml)

个人整理的系统与工程 PDF：逐本收录，保留版本、校验值和缺口说明。PDF 不进 git，全部放在 GitHub Releases；仓库只保存目录、元数据与校验脚本，clone 只有几十 KB。

> [!IMPORTANT]
> 《从内核到智能体》第七篇「完整嵌入式系统」**尚未整合完整**：当前 24 章是阶段性快照，后续以新版 PDF 更新，不覆盖旧文件。详见 [嵌入式现状](docs/嵌入式现状.md)。

## 收录

<!-- catalog:begin -->
共 1 本，合计 1140 页，13.1 MiB。

| 系列 | 书名 | 版本 | 页数 | 大小 | 状态 | 下载 |
|---|---|---|---|---|---|---|
| 从内核到智能体 | 从内核到智能体：系统原理解剖图解全集 | 2026.11 | 1140 | 13.1 MiB | ⚠️ 部分整合 | [PDF](<https://github.com/fieldnote-ops/pdf-shelf/releases/download/v2026.11/from-kernel-to-agent-2026.11.pdf>) |

状态说明：
- **从内核到智能体：系统原理解剖图解全集**：第七篇「完整嵌入式系统」尚未整合完整，详见 docs/嵌入式现状.md
<!-- catalog:end -->

上表由 `scripts/add_pdf.py` 从 [`catalog.yaml`](catalog.yaml) 生成；PDF 本身在 Releases，不在仓库里。

## 下载与校验

- 点表格里的 `PDF` 直接下载。Release 资产支持 HTTP Range，断了可以续传。
- 网络不稳时推荐用脚本：自动续传、下完校验 sha256。

```bash
scripts/fetch.sh system-atlas              # 下到当前目录
scripts/fetch.sh system-atlas ~/Downloads  # 下到指定目录
```

- 用 `gh` 也可以：

```bash
gh release download v2026.11 -p '*.pdf'
```

- 所有文件的哈希见 [`SHA256SUMS`](SHA256SUMS)。

## 怎么读

- 文件名带版本号（`YYYY.MM`），对应构建时的书内版本日期。
- 每册目录下有自己的 `README.md`，写这本书的结构、来源与已知缺口。
- 换版不覆盖旧文件：旧版留在原 tag 的 Release 里。

## 新增一本

见 [收录流程](docs/收录流程.md)。顺序是「登记 → 提交 → 打 tag → 发 Release → 上传资产」：

```bash
python3 scripts/add_pdf.py --file <PDF 路径> --id <ascii-id> --series <系列> \
  --title "<书名>" --version 2026.12
```

## 校验

```bash
python3 scripts/check_repo.py
```

只做离线一致性校验（catalog ↔ README ↔ SHA256SUMS），不下载 PDF、不访问网络；CI 在 push 时跑同一份脚本。

## 许可

- `pdfs/` 下的说明与正文：CC BY-NC-SA 4.0，见 [LICENSE](LICENSE)。
- `scripts/` 下的代码：MIT，见 [LICENSE-MIT](LICENSE-MIT)。

## 边界

只收录自己编写或有权发布的材料；第三方书籍（含译本）除非获得授权，不进入本仓库。
