---
name: webnovel-radar
description: |
  网文雷达——面向作者的网文行业新闻与平台政策监测。抓取起点/阅文、番茄、七猫、晋江、纵横、飞卢、刺猬猫、豆瓣阅读、掌阅等平台公告，以及国家新闻出版署、国家版权局、中央网信办等监管政策，汇总作者圈热点、争议与风险，按“对作者的影响”排序并输出中文简报。
  触发词：网文热点、网文新闻、网文日报、网文周报、平台政策、平台规则、合同变化、稿费变化、分成变化、审核收紧、下架、封书、处罚公告、网文圈今天有什么、起点最近改了什么、番茄最近改了什么、七猫最近改了什么、晋江最近改了什么、有什么新规、作者圈热点、网文维权、AI治理网文。
  当用户询问网文行业新闻、平台政策、作者权益、审核与稿费变化时使用。不要用于写小说、拆书、改稿或非网文新闻。
---

# 网文雷达 Webnovel Radar

## 目标

帮作者快速知道三件事：

1. **平台又改了什么**：签约、分成、稿费、全勤、审核、推荐、下架、处罚、征文。
2. **行业发生了什么**：监管政策、版权行动、IP 改编、短剧、出海、平台财报。
3. **作者圈在吵什么**：维权、抄袭、AI 洗稿、工作室、合同争议、人物故事。

默认只做资讯与政策监测，不写小说、不做写作建议。

## 数据源

完整清单见 `references/sources.md`。核心原则：

- 只抓**公开网页**，不登录、不使用 Cookie、不接付费 API。
- 官方政策优先，平台公告次之，行业媒体再次，社区传闻只做补充。
- 部分作者后台/论坛需登录，抓不到时如实标注“本次未覆盖”，不编造。
- 起点、扫黄打非、知乎等有反爬；直连失败时用 `https://r.jina.ai/<url>` 兜底。

## 工作流

### 第 0 步：选模式

| 用户说 | 模式 | 时间窗口 |
|---|---|---|
| 网文日报、今天有什么 | 日报 | 7d，优先 24-72h |
| 网文周报、本周 | 周报 | 7d |
| 番茄/起点/晋江最近改了什么 | 单平台 | 30d |
| 有什么新规、政策变化 | 政策专项 | 30-90d |
| 展开第 N 条 | 追问 | 按原条目 |

### 第 1 步：扫描公开源

默认命令（不跑搜索引擎，避免被限流）：

```bash
python .agents/skills/webnovel-radar/scripts/scan.py --all --since 7d --max-total 150 --search-budget 0
```

Windows 用 `python`，macOS/Linux 用 `python3`。直连失败时加代理：

```bash
python .agents/skills/webnovel-radar/scripts/scan.py --all --since 7d --search-budget 0 --proxy http://127.0.0.1:7897
```

脚本只把 JSON 打到 stdout，不写文件。JSON 里有：

- `sources[]`：每个源的 `status`（`direct`/`jina`/`search`/`empty`/`skipped`/`error`）、条数、错误
- `items[]`：标题、链接、日期、来源、分类、摘要片段

**补漏搜索**（一次只跑一个搜索源）：

```bash
python .agents/skills/webnovel-radar/scripts/scan.py --source fanqie_search --since 30d --search-budget 1
```

如果返回 `search blocked: HTTP 202`，说明搜索引擎临时限流：等 5-10 分钟重试一次；仍失败就跳过，用直连源出简报，并在末尾标注“搜索源本次未覆盖”。

### 第 2 步：筛选与分级

按 `references/ranking.md` 打分，优先保留：

1. 监管政策 / 平台规则变更
2. 签约、合同、稿费、分成、全勤、保底、买断
3. 审核、下架、封书、处罚、违规判定
4. 版权、抄袭、AI 洗稿、AI 使用规则
5. 流量、推荐、榜单、新书期
6. 征文、扶持、训练营
7. IP 改编、短剧、出海
8. 平台财报、行业数据
9. 作者维权、争议、人物故事

**可信度分级：**

- 官方公告（新闻出版署、版权局、网信办、平台官方公告）
- 权威媒体（中国作家网、正规行业媒体）
- 社区讨论（晋江论坛、龙空、贴吧、微博、小红书）
- 未证实传闻

传闻只能放“待确认”，不能进头条，不能写成事实。

### 第 3 步：抓关键原文

对政策/头条前 3-5 条，打开原文确认：

- 发布机构/平台
- 发布日期与生效日期
- 适用平台与作者范围
- 具体变更点
- 对作者的影响（钱、版权、审核、流量）
- 原文链接

页面打不开时：

1. 用 `https://r.jina.ai/<原文URL>` 再试一次
2. 仍失败就标注“原文未能打开，以下为标题/摘要信息”

### 第 4 步：输出简报

模板见 `references/output-template.md`。默认 10-15 条，政策优先。

硬规则：

- **只聊天，不保存报告文件、不建快照、不写本地状态**
- 每条必须有链接和日期；没有就标“日期未标注”
- 政策条目必须写“影响谁 / 作者怎么办 / 生效时间”
- 只做摘要，不复制全文
- 不把旧闻当新闻；超过 7 天标“旧闻回顾”
- 不把社区爆料当官方公告
- 不提供法律意见；提醒以官方原文为准

## 输出结构

```markdown
# 网文雷达 · 2026-11-08
> 数据窗口：过去 7 天 | 覆盖：起点/阅文、番茄、七猫、晋江、纵横、飞卢、豆瓣阅读 | 新增 N 条

## 一、政策与规则变更（按影响排序）
1. **标题**
   - 来源/日期/可信度：
   - 变化：
   - 影响谁：
   - 作者怎么办：
   - 生效/截止：
   - 原文：

## 二、平台与行业动态
## 三、作者圈热议与争议
## 四、风险预警
## 五、一句话总结
```

## 常用命令

```bash
# 列出所有信源
python .agents/skills/webnovel-radar/scripts/scan.py --list

# 只看监管政策
python .agents/skills/webnovel-radar/scripts/scan.py --category 监管政策 --since 30d --search-budget 0

# 只看平台规则
python .agents/skills/webnovel-radar/scripts/scan.py --category 平台规则 --since 7d --search-budget 0

# 单平台搜索补漏
python .agents/skills/webnovel-radar/scripts/scan.py --source qimao_search --since 30d --search-budget 1

# 包含登录受限/可选源
python .agents/skills/webnovel-radar/scripts/scan.py --all --include-optional --since 7d --search-budget 0
```

## 失败模式

| 情况 | 处理 |
|---|---|
| 近 7 天没有新政策 | 正常，写“近 7 天无新政策”，不要硬凑 |
| 搜索返回 202/429 | 跳过搜索，标“搜索源暂不可用”，用直连源 |
| 平台页面是 JS/需登录 | 用 Jina 或搜索补；仍失败标“本次未覆盖” |
| 日期缺失 | 标“日期未标注”，降低排序 |
| 反爬/SSL 失败 | 换 Jina；仍失败标缺口 |
| 同一政策多源报道 | 合并为一条，标“多源确认” |
| 社区爆料与官方冲突 | 官方口径优先，爆料放“待确认” |

## 参考文件

- `references/sources.md`：信源清单、访问方式、已知坑
- `references/policy-taxonomy.md`：政策分类、作者影响映射、可信度规则
- `references/ranking.md`：排序权重与扣分项
- `references/output-template.md`：日报/周报/政策专项/追问模板
