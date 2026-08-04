# A' 方案上手：盘前提醒 + 合并抄底信号

你已选择 **A'**：只用 Cursor Automations，开 **2 个** 定时任务。

---

## 第 1 步：让项目能被云端读到

Cloud Agent 读的是 **GitHub/GitLab 上的仓库**，不是你电脑上未推送的文件。

1. 把本文件夹建成 Git 仓库并推到 GitHub（若还没有）
2. 在 Cursor 连接该仓库（Settings / Cloud Agents / GitHub）
3. 之后改 `soul/`、`scheduler/` 要 **commit + push**，云端才会看到最新内容

可在本项目终端执行（需你本机已登录 `gh`）：

```bash
cd /Users/mac/Documents/invest-agent
git init
git add .
git commit -m "Initial invest-agent framework (A' scheduler)"
gh repo create invest-agent --private --source=. --remote=origin --push
```

若你希望我代为 `git init` / 提交，直接说一声即可（推远程需你授权）。

---

## 第 2 步：打开计费开关

1. 打开 [cursor.com/dashboard](https://cursor.com/dashboard)
2. 确认至少是 **Pro**
3. 开启 **On-demand usage**，设月消费上限（建议先 **$15–20**）
4. 上限附近留一点余量，否则 Cloud Agent 可能起不来

---

## 第 3 步：建 2 个 Automation

入口任选其一：

- 浏览器：[cursor.com/automations](https://cursor.com/automations)
- 或 Cursor **Agents Window** → Automations
- 或在 Agents Window 里用 `/automate`

### Automation ① 盘前提醒

| 项 | 填什么 |
|----|--------|
| 名称 | Invest Premarket Reminder |
| 触发 | Schedule / Cron：`0 21 * * 1-5`（若界面按 UTC，需换算；目标是北京时间工作日 21:00） |
| 仓库 | 选中你的 `invest-agent` 仓库 |
| 模型 | Composer 或 Sonnet（省钱选 Composer） |
| Instructions | 整段粘贴 `scheduler/prompt-premarket.md` 里「---」以下内容 |

### Automation ② 合并抄底信号

| 项 | 填什么 |
|----|--------|
| 名称 | Invest SPX+BTC Signals |
| 触发 | Cron：`0 9 * * *`（北京时间每天 09:00；注意时区换算） |
| 仓库 | 同上 |
| 模型 | 同上 |
| Instructions | 整段粘贴 `scheduler/prompt-signals.md` 里「---」以下内容 |

**时区提醒**：Cursor cron 若按 UTC，北京时间 21:00 = UTC `0 13 * * 1-5`；北京 09:00 = UTC `0 1 * * *`。以界面标注为准。

---

## 第 4 步：先手动跑一次

每个 Automation 里找 **Run now / 立即运行**，确认：

- `output/daily/premarket-….md` 或 `output/signals/daily-….md` 有文件
- 内容没有明显编造；缺数据应写「未获取」

然后 `git pull`（若 Agent 通过 PR/commit 回写）或在 Cloud Agent 结果里查看产出。

---

## 第 5 步：观察一周成本

- 看 [Usage](https://cursor.com/dashboard/usage)
- 目标：两项合计大约 **$15–30/月**
- 偏贵 → 换更便宜模型、缩短提示词、减少搜索次数

---

## 暂不要开

财经日报、周报、月报、选题 —— 已在 `scheduler/rules.md` 标为 ⏸，等 A' 稳定再加。
