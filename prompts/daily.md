今天是 {{DATE}}（Asia/Shanghai）。请执行「网文雷达」日报任务，供定时任务自动推送。

1. 加载 webnovel-radar skill（skill ID: `webnovel-radar`），严格按它的工作流、分级规则和输出模板执行。
2. 运行扫描（服务器直连国内站点，不要手动加 `--proxy`；脚本会自动读取 `HTTPS_PROXY`）：
   `python3 .agents/skills/webnovel-radar/scripts/scan.py --all --since 7d --max-total 150 --search-budget 0`
   如果直连源覆盖不足，再用单个搜索源补漏：
   `python3 .agents/skills/webnovel-radar/scripts/scan.py --source fanqie_search --since 7d --search-budget 1`
   搜索源返回 202/429 就跳过，并在报告末尾标注「搜索源本次未覆盖」。
3. 按 skill 的排序规则筛选，默认 10-15 条，政策与规则变更优先；近 7 天没有新政策就如实写「近 7 天无新政策」，不要硬凑。
4. 对政策条目和头条前 3-5 条，用 webfetch 打开原文核实发布方、日期、生效时间、适用范围；打不开就改用 `https://r.jina.ai/<原文URL>`，仍失败则标注「原文未能打开，以下为标题/摘要信息」。
5. 每条必须有链接和日期；日期缺失标「日期未标注」。传闻只能放「待确认」，不能当事实。超过 7 天的内容标「旧闻回顾」。
6. 把最终 Markdown 简报写入 `{{REPORT_PATH}}`（这是定时任务的硬要求，覆盖 skill 中「不保存报告文件」的默认规则）。报告采用 skill 的日报模板，包含：政策与规则变更、平台与行业动态、作者圈热议与争议、风险预警、一句话总结。
7. 不要在聊天里重复报告全文；完成后只回复一行：`报告已写入 {{REPORT_PATH}}，共 N 条`。
8. 不要提问、不要等待确认；遇到不确定或抓取失败，按 skill 的失败模式处理并继续。
