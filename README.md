# daily-news

每天北京时间 08:00，在 Ubuntu 服务器上通过 `opencode run` 调用 `webnovel-radar` skill 生成网文雷达日报，并用 Server酱推送到手机。

- 日报和日志只保存在服务器，报告保留 7 天、日志保留 14 天
- 报告不提交 git，避免每天产生提交
- 推送失败会再发一条告警，并保留当天报告方便手动重发

## 目录结构

```text
.agents/skills/webnovel-radar/   网文雷达 skill（扫描脚本 + 参考文档）
prompts/daily.md                 日报提示词模板
scripts/run_daily.sh             定时任务入口
scripts/push_serverchan.py       Server酱推送（兼容 Turbo / Server酱³）
deploy/webnovel-radar.service    systemd 服务
deploy/webnovel-radar.timer      systemd 定时器
.env.example                     配置模板
```

## 服务器部署

```bash
# 基础依赖；ripgrep 是 opencode 的搜索依赖，缺失时它会尝试从 GitHub 下载并可能卡住
sudo apt update && sudo apt install -y git python3 curl ca-certificates ripgrep

# 安装 opencode，固定与本地一致的 1.19.0
curl -fsSL https://opencode.ai/install | bash -s -- --version 1.19.0
```

如果 `opencode.ai` 报 `Connection reset`，改用 npm 镜像安装同一个二进制：

```bash
(
set -euo pipefail
arch="$(uname -m)"
case "$arch" in
  x86_64) pkg="opencode-linux-x64" ;;
  aarch64|arm64) pkg="opencode-linux-arm64" ;;
  *) echo "unsupported arch: $arch"; exit 1 ;;
esac
if [[ "$pkg" == "opencode-linux-x64" ]] && ! grep -qwi avx2 /proc/cpuinfo; then
  pkg="opencode-linux-x64-baseline"
fi
ver="1.19.0"
tmp="$(mktemp -d)"
curl -fL --retry 3 -o "$tmp/opencode.tgz" "https://registry.npmmirror.com/${pkg}/-/${pkg}-${ver}.tgz"
tar -xzf "$tmp/opencode.tgz" -C "$tmp"
mkdir -p "$HOME/.opencode/bin"
install -m 755 "$tmp/package/bin/opencode" "$HOME/.opencode/bin/opencode"
rm -rf "$tmp"
export PATH="$HOME/.opencode/bin:$PATH"
opencode --version
)
grep -q '.opencode/bin' ~/.bashrc || echo 'export PATH="$HOME/.opencode/bin:$PATH"' >> ~/.bashrc
```

拉取仓库：

```bash
git clone https://github.com/xifeinan-creator/daily-news.git ~/daily-news
cd ~/daily-news
```

如果服务器访问 GitHub 超时，可以在本地打包后通过 `scp` 上传：

```bash
# 本地（在仓库根目录执行）
tar -czf ../daily-news-upload.tar.gz --exclude=.git --exclude=reports --exclude=logs .
scp ../daily-news-upload.tar.gz ecs-user@<服务器IP>:~/

# 服务器
mkdir -p ~/daily-news
tar -xzf ~/daily-news-upload.tar.gz -C ~/daily-news
cd ~/daily-news
```

配置密钥并手动试跑：

```bash
# 密钥放在仓库外，避免被 agent 或 git 碰到
mkdir -p ~/.config/webnovel-radar
cp -n .env.example ~/.config/webnovel-radar/env
chmod 600 ~/.config/webnovel-radar/env
# 编辑 ~/.config/webnovel-radar/env，至少填写 DEEPSEEK_API_KEY 和 SERVERCHAN_SENDKEY

# 手动跑一次，确认报告生成且手机收到
./scripts/run_daily.sh
ls -l reports/
```

确认无误后安装定时器：

```bash
mkdir -p ~/.config/systemd/user
cp deploy/webnovel-radar.service deploy/webnovel-radar.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now webnovel-radar.timer
sudo loginctl enable-linger "$USER"
```

如果仓库不在 `~/daily-news`，修改 `deploy/webnovel-radar.service` 里的 `WorkingDirectory` 和 `ExecStart` 后重新复制。

## 配置项

| 变量 | 必填 | 默认 | 说明 |
|---|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | - | DeepSeek API Key |
| `SERVERCHAN_SENDKEY` | 是 | - | Server酱 SendKey，`SCT...` 或 `sctp...` |
| `SERVERCHAN_API_URL` | 否 | 自动识别 | 自定义推送地址 |
| `OPENCODE_MODEL` | 否 | `deepseek/deepseek-flash` | opencode 模型 |
| `OPENCODE_BIN` | 否 | `~/.opencode/bin/opencode` | opencode 路径 |
| `REPORT_KEEP_DAYS` | 否 | `7` | 报告保留天数 |
| `LOG_KEEP_DAYS` | 否 | `14` | 日志保留天数 |
| `REPORT_TZ` | 否 | `Asia/Shanghai` | 报告时区 |
| `HTTPS_PROXY` | 否 | - | 海外服务器访问国内站点时使用 |

配置默认读取 `~/.config/webnovel-radar/env`；不存在时回退到仓库根目录的 `.env`。也可以用 `ENV_FILE` 环境变量指定其他路径。配置文件由 bash 直接 source，值含空格时请用引号包裹。

## 日常运维

```bash
# 查看下次执行时间
systemctl --user list-timers | grep webnovel

# 立即手动触发一次
systemctl --user start webnovel-radar.service

# 查看最近日志
journalctl --user -u webnovel-radar -n 100 --no-pager

# 校验定时表达式
systemd-analyze calendar "*-*-* 08:00:00 Asia/Shanghai"

# 查看服务状态
systemctl --user status webnovel-radar.timer
```

更新代码：

```bash
# 如果服务器是 git clone 的
cd ~/daily-news && git pull

# 如果是 scp 上传的（没有 .git），重新打包上传后解压覆盖
# 本地（在仓库根目录执行）：
tar -czf ../daily-news-upload.tar.gz --exclude=.git --exclude=reports --exclude=logs .
scp ../daily-news-upload.tar.gz ecs-user@<服务器IP>:~/
# 服务器：
tar -xzf ~/daily-news-upload.tar.gz -C ~/daily-news
```

## 当前部署状态（2026-11-09）

- 服务器：Ubuntu 24.04，opencode 1.19.0，ripgrep 已安装
- 定时器：已启用，每天 08:00（`Asia/Shanghai`），`Persistent=true`，`Linger=yes`
- 首次手动运行：成功生成 14 条日报并推送
- 服务器代码通过 tarball + scp 部署，没有 `.git`
- 已知网络限制：GitHub 与 opencode.ai 不稳定；`r.jina.ai` 不可达；报告会在末尾标注本次未覆盖的源
- 报告与日志只在服务器：报告保留 7 天，日志保留 14 天

## 排查

- **安装 opencode 时报 `Connection reset`**：国内服务器访问 `opencode.ai` 不稳定，改用上面的 npmmirror 安装方式。
- **`git clone` 超时**：服务器到 GitHub 的 Git 连接不稳定，改用本地打包 + `scp` 上传。
- **opencode 启动卡住，日志出现 `downloading ripgrep`**：先执行 `sudo apt install -y ripgrep`，确认 `rg --version` 可用。
- **opencode 未找到**：确认 `~/.opencode/bin/opencode` 存在，或在 `.env` 设置 `OPENCODE_BIN`。
- **报告未生成**：查看 `logs/run-YYYY-MM-DD.log` 和 `journalctl --user -u webnovel-radar`；脚本会自动重试一次。
- **搜索源返回 202/429**：属正常限流，日报会继续使用直连源，并在文末标注“搜索源本次未覆盖”。
- **Server酱 429**：24 小时内调用超限，脚本不会反复重试，次日恢复。
- **推送内容过长**：Server酱正文约 32KB，脚本会自动截断并注明；完整报告仍在服务器 `reports/`。
- **想保留更久**：调整 `.env` 里的 `REPORT_KEEP_DAYS` / `LOG_KEEP_DAYS`。
- **换机器/换用户**：`opencode` 的鉴权数据在用户目录下；使用环境变量 `DEEPSEEK_API_KEY` 时无需交互登录。
