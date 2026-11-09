# daily-news

## 定时任务约定

- 本项目由服务器 systemd timer 每天北京时间 08:00 调用 `scripts/run_daily.sh`，该脚本执行 `opencode run`。
- 生成网文雷达日报时，必须把最终 Markdown 简报写入 `reports/webnovel-radar-YYYY-MM-DD.md`。这是本仓库对 `webnovel-radar` skill「默认只在聊天输出、不保存文件」规则的显式覆盖。
- 报告写入后，聊天中只回复一行确认（路径 + 条数），不要重复全文。
- 不要提问、不要等待人工确认；遇到抓取失败按 skill 的失败模式处理，并在报告中标注缺口。
- 不要在报告、日志、聊天中输出 `.env` 里的任何密钥（`DEEPSEEK_API_KEY`、`SERVERCHAN_SENDKEY`）。
- 不修改 `.agents/skills/` 下的 skill 文件；运行约定写在本文件。
