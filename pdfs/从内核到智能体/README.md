# 从内核到智能体：系统原理解剖图解全集

- 下载：[from-kernel-to-agent-2026.11.pdf](<https://github.com/fieldnote-ops/pdf-shelf/releases/download/v2026.11/from-kernel-to-agent-2026.11.pdf>)（13.1 MiB）
- 版本：2026.11，2026-11-18 构建
- 规模：两卷八篇，1140 页
- sha256：`5d6d3625ba3c366cdf3aff11f54fe1eb5f8d38e871cdca32c59b2e986eda4516`
- 构建：Typst 0.15.1，`ALL_BOOK_PROFILE=full`
- 许可：CC BY-NC-SA 4.0

## 结构

| 篇 | 主题 | 章数 |
|---|---|---|
| 第零篇 | 统一认知模型：结构、代价、行为、一致性、系统论收束 | 8 章 / 47 节 |
| 第一篇 | Redis：事件循环、数据结构、持久化、复制、哨兵、集群 | 12 |
| 第二篇 | Rust：所有权、借用、生命周期、trait、并发、异步底层 | 19 |
| 第三篇 | PostgreSQL 18：进程内存、页元组、MVCC、WAL、索引、查询、复制 | 13 |
| 第四篇 | Linux 操作系统层：引导链、内核、用户空间、图形栈、桌面集成 | 16 |
| 第五篇 | Temporal 持久执行：事件历史、确定性重放、重试与幂等、版本演进 | 22 |
| 第六篇 | Agent Harness：装配、循环、上下文、工具、权限、可追溯、编排 | 14 |
| 第七篇 | 完整嵌入式系统：复位、测量、FreeRTOS、控制、通信、低功耗、OTA | 24 |

两卷不是上下级关系：主卷沿系统栈展开，嵌入式卷以「复位 → 闭环」独立成篇，两者通过「样本 + 时间戳 → 缓冲 → 任务 → 截止期」这条线连接。

## 已知缺口

**第七篇「完整嵌入式系统」尚未整合完整。** 本版收录 24 章（书内 p991–1118），覆盖复位、测量、RTOS、控制、通信、低功耗、OTA 与证据的当前链路，是阶段性快照；章节级补全后以新版 PDF 发布，不覆盖本文件。范围与判断依据见 [嵌入式现状](../../docs/嵌入式现状.md)。

## 下载与校验

PDF 由 Release 托管，不在 git 里。推荐：

```bash
scripts/fetch.sh system-atlas
```

也可用 `gh release download v2026.11 -p '*.pdf'`；哈希见 [`SHA256SUMS`](../../SHA256SUMS)。
