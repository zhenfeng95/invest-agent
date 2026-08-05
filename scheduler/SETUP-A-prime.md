# A' 方案上手：美股盘前提醒 + A股盘前提醒

你已选择 **A'**：只用 Cursor Automations，开 **2 个** 定时任务。

**当前组合**：
1. **美股盘前提醒**（工作日 21:00）
2. **A股盘前提醒**（工作日 09:00）— 大盘 + 东财行业板块 + A股持仓 + 要闻 + 意见建议

**已停用**：合并抄底信号（SPX + BTC）。若 Automations 里还有旧任务，请 **Pause / 删除**。

**通知渠道**：邮件 → `zhenfengxiaoge@outlook.com`（不再靠 GitHub PR 提醒）。  
**存档方式**：仍写入 `output/` 并 commit / push；**不开 PR**。

---

## 第 1 步：让项目能被云端读到

Cloud Agent 读的是 **GitHub/GitLab 上的仓库**，不是你电脑上未推送的文件。

1. 把本文件夹建成 Git 仓库并推到 GitHub（若还没有）
2. 在 Cursor 连接该仓库（Settings / Cloud Agents / GitHub）
3. 之后改 `soul/`、`scheduler/`、`data/raw/trades/` 要 **commit + push**，云端才会看到最新持仓

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

## 第 3 步：接入 Resend（发邮件）

Cursor Automations **没有原生邮件工具**，用官方 [Resend MCP](https://resend.com/docs/mcp-server)。

### 3.1 注册并拿 API Key

1. 打开 [resend.com](https://resend.com)，建议用 **`zhenfengxiaoge@outlook.com` 注册**（未验证自有域名时，免费测试发信只能发到账号邮箱）
2. [API Keys](https://resend.com/api-keys) → Create → 权限选 **Full Access**（或至少能发信）
3. 复制 `re_…` 密钥（只显示一次）

未绑域名时发件人一般是 `onboarding@resend.dev`，够用。以后若要自定义发件人，再在 Resend 验证域名。

### 3.2 挂到 Automation（不是 IDE 本地 MCP）

**Automations 不会复用 Cursor IDE 里的 MCP**，必须在每个 Automation 里单独加：

1. 打开 [cursor.com/automations](https://cursor.com/automations) → 编辑对应任务
2. Tools → **MCP server** → 添加 Resend  
   - URL：`https://mcp.resend.com/mcp`  
   - Header：`Authorization: Bearer re_你的密钥`
3. 保存后用 **Run now** 测一次是否真能发到邮箱

可选：本地对话也想测发信，可在 Cursor Settings → MCP 加同一套配置；与云端定时任务互不影响。

---

## 第 4 步：建 / 改 2 个 Automation

入口任选其一：

- 浏览器：[cursor.com/automations](https://cursor.com/automations)
- 或 Cursor **Agents Window** → Automations
- 或在 Agents Window 里用 `/automate`

### 共用设置（两个任务都要）

| 项 | 填什么 |
|----|--------|
| 仓库 | `invest-agent` 的 `main` |
| 模型 | Composer 或 Sonnet（省钱选 Composer） |
| Tools | ✅ **MCP：Resend**；❌ **关闭 Create pull request**（不要开 PR） |
| 通知 | 靠邮件，不要依赖 GitHub 邮件/PR 提醒 |

### Automation ① 美股盘前提醒

| 项 | 填什么 |
|----|--------|
| 名称 | Invest Premarket Reminder |
| 触发 | Schedule / Cron：`0 21 * * 1-5`（若界面按 UTC，需换算；目标是北京时间工作日 21:00） |
| Instructions | 整段粘贴 `scheduler/prompt-premarket.md` 里「---」以下内容 |

### Automation ② A股盘前提醒（替换原「合并抄底信号」）

| 项 | 填什么 |
|----|--------|
| 名称 | Invest A-Share Premarket |
| 触发 | Cron：`0 9 * * 1-5`（北京时间工作日 09:00；注意时区换算） |
| Instructions | 整段粘贴 `scheduler/prompt-ashare-premarket.md` 里「---」以下内容 |

若以前建过 **Invest SPX+BTC Signals**：请 **Pause 或删除**，避免与 A股盘前抢同一时段、重复扣费。

**时区提醒**：Cursor cron 若按 UTC，北京时间 21:00 = UTC `0 13 * * 1-5`；北京 09:00 = UTC `0 1 * * 1-5`。以界面标注为准。

若 Automation 已建过：只需 **更新名称/Instructions**、**关掉 Create PR**、**加上 Resend MCP**，不必强行新建。

**想更早收到**：可把 A股任务改成 `0 8 * * 1-5`（北京 08:00），并同步改 `rules.md`。

---

## 第 5 步：先手动跑一次

每个 Automation 里找 **Run now / 立即运行**。

### 成功时你应该看到什么

1. **邮箱** `zhenfengxiaoge@outlook.com` 收到邮件（主题含「盘前提醒」或「A股盘前提醒」）
2. **Automation 运行详情**：成功；摘要里有文件路径；**没有**「Opened pull request」
3. **GitHub `main`**：`output/daily/` 出现新 md（若 Agent 已 push）  
4. 本机：`git pull` 后本地 `output/` 同步

若邮件没到：查垃圾箱 → 查 Resend Dashboard 投递记录 → 确认 Automation 里 MCP 已授权。

若 `main` 上仍无新文件、但邮件有了：说明 push 权限可能受限——**以邮件为准**；可在运行详情里下载产物，或放宽 Cloud Agent 对仓库的写权限后再试。

### 若跑完仍是空的（排查）

| 检查项 | 怎么做 |
|--------|--------|
| 运行是否成功 | Automations → 该任务 → Runs，是否 Failed |
| 有没有邮件 | Outlook 收件箱 / 垃圾箱；Resend 投递日志 |
| Resend MCP | Automation Tools 里是否已接且鉴权成功 |
| 是否误开 PR | 关掉 Create pull request；提示词已改为「不要开 PR」 |
| 提示词是否最新 | push 最新 `prompt-*.md` 后，把 Instructions 再粘贴一遍 |
| 仓库/分支是否选对 | 必须是你的 `invest-agent` 的 `main` |
| A股持仓是否为空 | 确认已 push `data/raw/trades/` |

改完提示词后：**先 push 到 main**，再在 Automations 里把 Instructions 更新成最新内容，然后 **再点一次立即运行**。

确认：

- 邮件正文含大盘 / 板块 / 持仓 / 要闻 / **意见与建议**
- 缺数据应写「未获取」，未明显编造

---

## 第 6 步：观察一周成本

- 看 [Usage](https://cursor.com/dashboard/usage)
- 目标：两项合计大约 **$15–30/月**（Resend 免费额度对个人投研足够）
- 偏贵 → 换更便宜模型、缩短提示词、减少搜索次数

---

## 暂不要开

财经日报、周报、月报、选题、抄底信号 —— 已在 `scheduler/rules.md` 标为 ⏸，等 A' 稳定再加。
