# 网文雷达信源清单

配置文件：`scripts/sources.json`。`scan.py` 按这里的 `id` 扫描；加源、改源只改这个 JSON，不改脚本。

## 访问状态说明

| 状态 | 含义 |
|---|---|
| `direct` | 直连成功 |
| `jina` | 直连失败，走 `r.jina.ai` 成功 |
| `search` | 搜索引擎发现（只有标题/摘要，日期常缺失） |
| `empty` | 页面能打开，但时间窗口内没有符合条件的条目 |
| `skipped` | 本次未执行（搜索预算或可选源未启用） |
| `error` | 抓取失败或被拦截；简报里要标注覆盖缺口 |

## 一、监管政策

| ID | 名称 | 入口 | 访问/备注 |
|---|---|---|---|
| `nppa_notice` | 国家新闻出版署-通知公示 | https://www.nppa.gov.cn/xxfb/tzgs/ | 直连稳定；标题在页面脚本里，脚本已做 `_docTitle` 解析 |
| `nppa_policy` | 国家新闻出版署-政策解读 | https://www.nppa.gov.cn/xxgk/zcjd/ | 直连稳定；无新内容时为空 |
| `ncac` | 国家版权局 | https://www.ncac.gov.cn/ | 直连稳定；日期可从 URL 解析 |
| `cac` | 中央网信办 | https://www.cac.gov.cn/ | 直连稳定；关注内容治理、AI、未成年人保护 |
| `chinawriter_netlit` | 中国作家网-网络文学 | https://www.chinawriter.com.cn/404022/index.html | 直连稳定；网络文学评奖、扶持、行业讨论 |
| `chinawriter_home` | 中国作家网 | https://www.chinawriter.com.cn/ | 直连稳定；范围更广，需筛网文相关 |
| `shdf` | 中国扫黄打非网 | https://www.shdf.gov.cn/ | 可选；常被 521 拦截，走 Jina，仍可能失败 |

**政策类重点看：** 出版管理、内容审核、未成年人保护、AI 生成内容标识、版权专项行动、网络文学精品工程、作品扶持与评奖。

## 二、平台规则与公告

| ID | 平台 | 入口 | 访问/备注 |
|---|---|---|---|
| `yuewen_article` | 阅文/起点作家专区-最新文章 | https://write.qq.com/portal/article | 直连稳定；公告、福利、征文、创作课堂 |
| `yuewen_welfare` | 阅文作家专区-作家福利 | https://write.qq.com/portal/college/editordetail | 单页政策入口 |
| `qidian_news` | 起点-公告频道 | https://www.qidian.com/news/index | 可选；直连 202，走 Jina；多为新书资讯，政策以阅文作家专区为准 |
| `fanqie_changelog` | 番茄-作家专区版本公告 | https://fanqienovel.com/writer/zone/change-log | JS 页面，走 Jina，抓正文摘要 |
| `fanqie_search` | 番茄-公告搜索 | 搜索 `site:fanqienovel.com` | 搜索源；可发现签约模式、低质治理、处罚公告 |
| `yuewen_search` | 阅文/起点-公告搜索 | 搜索 `site:write.qq.com` | 搜索源；补漏 |
| `qimao_welfare` | 七猫-作家签约政策/福利 | https://www.qimao.com/fuli/ | JS 页面，走 Jina；签约模式、稿费、福利 |
| `qimao_publish` | 七猫-作品登载规则 | https://www.qimao.com/publish | JS 页面，走 Jina；内容规范与审核 |
| `qimao_notice` | 七猫-动态公告 | https://www.qimao.com/site/notice-1/ | 公告列表；链接是 JS，保留标题并指向列表页 |
| `qimao_search` | 七猫-公告搜索 | 搜索 `site:qimao.com` | 搜索源；补漏 |
| `jjwxc_help` | 晋江-帮助中心 | https://help.jjwxc.net/index.php?c_id=139 | 单页入口；具体规则分散 |
| `jjwxc_search` | 晋江-公告/规则搜索 | 搜索 `site:jjwxc.net` / `site:help.jjwxc.net` | 搜索源；补签约、审核、合同条目 |
| `jjwxc_home` | 晋江文学城 | https://www.jjwxc.net/ | 直连或 Jina；公开公告较少 |
| `zongheng_help` | 纵横-帮助中心 | https://doc.zongheng.com/help/2/SIGN_UP.html | 单页政策入口 |
| `zongheng_welfare` | 纵横-作者福利 | https://doc.zongheng.com/welfare/zongheng | 单页政策入口 |
| `faloo_news` | 飞卢-新闻公告 | https://b.faloo.com/News.aspx | 可选；页面多为 JS/导航，公开公告少 |
| `faloo_search` | 飞卢-公告搜索 | 搜索 `site:faloo.com` | 搜索源；补漏 |
| `ciweimao_author` | 刺猬猫作者平台 | https://author.ciweimao.com/ | 可选；多数内容登录后可见 |
| `douban_contract` | 豆瓣阅读-签约福利 | https://read.douban.com/submit/contract_benefit | 单页政策入口 |
| `zhangyue` | 掌阅 | https://www.zhangyue.com/ | 可选；页面偏 JS，公开公告少 |

**平台类重点看：** 签约模式、分成/保底/买断、全勤、稿费发放、审核标准、违规处罚、AI 使用规则、推荐机制、新书期、完结要求、征文与扶持。

## 三、作者社区

| ID | 名称 | 入口 | 访问/备注 |
|---|---|---|---|
| `jjwxc_bbs` | 晋江-网友交流区 | http://bbs.jjwxc.net/ | 公开论坛；适合争议、审核吐槽、维权讨论 |
| `lkong_home` | 龙空-首页 | https://www.lkong.com/ | 可选；论坛版块需登录，公开首页仅作补充 |

社区内容只能作为“作者圈热议/待确认”，不能当官方公告。引用时保留原帖链接，不传播未证实的指控。

## 四、行业动态

| ID | 名称 | 入口 | 访问/备注 |
|---|---|---|---|
| `yuewen_home` | 阅文集团 | https://www.yuewen.com/ | 直连；财报、IP、短剧、出海、AI |
| `guduomedia` | 骨朵网络影视 | https://www.guduomedia.com/ | 可选；直连 SSL 失败，走 Jina；IP 改编/短剧信号 |
| `industry_search` | 网文行业搜索 | 搜索“网文 政策/平台/稿费/签约/审核/AI/短剧” | 搜索源；补行业媒体与作者圈报道 |

## 五、搜索源与限流

搜索使用 DuckDuckGo Lite（`https://lite.duckduckgo.com/lite/`）。特点：

- 只用短 UA，不带 `Accept`/`Accept-Language`，否则容易被判异常。
- 同 IP 连续查询容易返回 `HTTP 202`。
- 默认命令用 `--search-budget 0`，不跑搜索；需要补漏时一次只跑一个搜索源（`--search-budget 1`）。
- 返回 202 时：等 5-10 分钟重试一次；仍失败就跳过，用直连源出简报，并标注“搜索源未覆盖”。

搜索源适合“补漏”，不适合作为唯一数据源。政策与平台规则优先用直连官方页面。

## 六、已知覆盖缺口

- **龙空论坛**：版块需要登录，公开首页信息有限。
- **番茄公告中心**：`notice.fanqienovel.com/docs` 是 JS 应用，直连/ Jina 都难拿列表，用 `fanqie_search` 补。
- **番茄/七猫作家后台**：`writer.fanqienovel.com`、`writer.qimao.com` 直连 SSL/422，公开页只做补充。
- **起点公告频道**：直连 202，走 Jina；内容偏新书资讯，政策以阅文作家专区为准。
- **扫黄打非网**：常被 521 拦截，可能抓不到。
- **微博/小红书/抖音/知乎**：无公开稳定接口，默认不抓；用户点名时可用联网搜索补，但必须标“社区来源/待确认”。
- **付费/登录内容**：不抓、不绕、不猜。

## 七、加源/改源

在 `scripts/sources.json` 里加一条：

```json
{
  "id": "example_source",
  "name": "示例来源",
  "category": "平台规则",
  "type": "url",
  "url": "https://example.com/news/",
  "access": "auto",
  "accept_all": false,
  "require_date": true,
  "keywords": ["公告", "规则", "签约", "审核"],
  "max_items": 20,
  "note": "说明"
}
```

字段说明：

- `type`：`url`（列表页）、`page`（单页政策）、`search`（搜索引擎）
- `access`：`auto`（直连→Jina）、`jina`（直接 Jina）、`search`
- `accept_all`：`true` 时列表页所有带日期/政策关键词的条目都收；`false` 时按 `keywords` 过滤
- `require_date`：`true` 时无日期条目不收，适合政府/媒体列表页
- `allow_js_links`：`true` 时允许 `javascript:void(0)` 链接，保留标题并指向列表页
- `block_url_patterns`：过滤小说阅读页等噪音 URL
- `optional`：`true` 时默认不扫，加 `--include-optional` 才扫

改完用 `python scripts/scan.py --list` 检查，再单独扫这个源验证。
