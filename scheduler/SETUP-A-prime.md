# A' 方案上手：美股盘前提醒 + A股盘前提醒

你已选择 **A'**：只用 Cursor Automations，开 **2 个** 定时任务。

**当前组合**：
1. **美股盘前提醒**（工作日 21:00）— 财报/经济数据/期权/技术位短提醒（见 `prompt-premarket.md`）
2. **A股盘前提醒**（工作日 09:00）— 市场状态判断/评分 + 昨日大盘/资金面/板块/持仓复盘 + 持仓近7日负面消息 + 当日盘前要闻 + 今日应对

**已停用 / 暂缓**：美股收盘日报（成本偏高，见 `prompt-us-close-daily.md`）；合并抄底信号（SPX + BTC）。若 Automations 里还有「美股收盘日报」任务，请 **Pause / 删除**。

**通知渠道**：**仅飞书**（自定义机器人 Webhook）。不再发邮件 / 不再用 Resend。  
**存档方式**：仍写入 `output/` 并 commit / push；**不开 PR**。飞书推送与 md **等价完整正文**（请求体约 20KB 上限，超长才截断）。

---

## 第 1 步：让项目能被云端读到

Cloud Agent 读的是 **GitHub/GitLab 上的仓库**，不是你电脑上未推送的文件。

1. 把本文件夹建成 Git 仓库并推到 GitHub（若还没有）
2. 在 Cursor 连接该仓库（Settings / Cloud Agents / GitHub）
3. 之后改 `soul/`、`scheduler/`、`data/raw/trades/` 要 **commit + push**，云端才会看到最新持仓

---

## 第 2 步：打开计费开关

1. 打开 [cursor.com/dashboard](https://cursor.com/dashboard)
2. 确认至少是 **Pro**
3. 开启 **On-demand usage**，设月消费上限（建议先 **$15–20**）
4. 上限附近留一点余量，否则 Cloud Agent 可能起不来

---

## 第 3 步：接入飞书（自定义机器人）

### 3.1 建机器人并拿 Webhook

> 官方路径：[自定义机器人使用指南](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)

**必须用飞书电脑客户端（PC）**；手机端 / 网页版通常看不到「自定义机器人」。不要去开放平台找。

1. 先建一个**群**（可建「只有自己」的测试群；单聊 / 私聊没有此入口）
2. 进入该群 → 右上角 **···** 或设置图标 → **设置** → **群机器人** → **添加机器人**
3. 在列表里点 **自定义机器人**（通常在最上面）→ 填名称（建议 `投研 Agent`）→ **添加**
4. 复制 Webhook URL（形如 `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx`）→ **完成**
5. 安全设置：先别开签名；可选「自定义关键词」并设为 `盘前`（则消息正文须含该词）。开了签名要改提示词，跟我说一声

#### 找不到「自定义机器人」时

| 原因 | 怎么办 |
|------|--------|
| 用了手机 / 网页版 | 改用 **PC 客户端** |
| 在单聊 / 会话里找 | 必须进 **群聊** |
| 企业租户关掉了能力 | 换个人号建私人群试；或问管理员是否禁用群自定义机器人 |
| 无添加权限 | 需群主/管理员，或自己建新群 |
| 只看到一堆应用机器人 | 列表顶部或搜索「自定义」；点的是 **添加机器人** 后的弹窗，不是开放平台 |

**不要把 Webhook URL commit 进仓库。**

### 3.2 把 URL 贴进每个 Automation（不是 IDE 本地 MCP）

每个 Automation 的 Instructions = **仓库提示词全文** + 文末密钥段：

```text
## 密钥（勿提交仓库；仅存在本 Automation）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的token
```

两个任务（美股盘前、A股盘前）都要贴同一段密钥。

可选：本机自测可把 URL 写进本地 `.env`（已 gitignore），与云端任务互不影响。

### 3.3 可卸掉 Resend

若 Automation Tools 里还挂着 Resend MCP：**删除 / 关掉** 即可，本方案不再需要。

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
| Tools | ❌ **不要开** Send to Slack / Teams / Open Pull Request；可选 Memories；飞书靠提示词里的 `curl`（Cloud Agent **自带终端**，Tools 列表里没有单独的 Shell 项） |
| 通知 | 靠飞书 Webhook，不要依赖 Slack / 邮件 / GitHub |

### Automation ① 美股盘前提醒

| 项 | 填什么 |
|----|--------|
| 名称 | Invest Premarket Reminder |
| 触发 | Schedule / Cron：`0 21 * * 1-5`（若界面按 UTC，需换算；目标是北京时间工作日 21:00） |
| Instructions | 粘贴 `scheduler/prompt-premarket.md`「---」以下内容 + 文末 `FEISHU_WEBHOOK_URL=...` |

若以前建过 **Invest US Close Daily**（美股收盘 08:00）：请 **Pause 或删除**。若盘前任务已 Pause，重新 **Enable** 并确认 Instructions 为最新 `prompt-premarket.md`。

### Automation ② A股盘前提醒

| 项 | 填什么 |
|----|--------|
| 名称 | Invest A-Share Premarket |
| 触发 | Cron：`0 9 * * 1-5`（北京时间工作日 09:00；注意时区换算） |
| Instructions | 粘贴 `scheduler/prompt-ashare-premarket.md`「---」以下内容 + 文末 `FEISHU_WEBHOOK_URL=...` |

若以前建过 **Invest SPX+BTC Signals**：请 **Pause 或删除**。

**时区提醒**：Cursor cron 若按 UTC：北京 21:00 = UTC `0 13 * * 1-5`；北京 09:00 = UTC `0 1 * * 1-5`。以界面标注为准。

若 Automation 已建过：只需 **更新 Instructions（含飞书密钥）**、**关掉 Create PR**、**去掉 Resend**，不必强行新建。

---

## 第 5 步：先手动跑一次

每个 Automation 里找 **Run now / 立即运行**。

### 成功时你应该看到什么

1. **飞书群**收到机器人消息（标题含「盘前提醒」或「A股盘前提醒」）
2. **Automation 运行详情**：成功；摘要里有文件路径与飞书 `code:0`；**没有**「Opened pull request」
3. **GitHub `main`**：`output/daily/` 出现新 md（若 Agent 已 push）
4. 本机：`git pull` 后本地 `output/` 同步

若飞书没到：核对 Webhook URL 是否贴对 → 机器人是否还在群里 → 运行日志里 `curl` 响应（非 0 看飞书错误码）→ 是否误开了签名却未算 sign。

若 `main` 上仍无新文件、但飞书有了：说明 push 权限可能受限——**以飞书为准**；可在运行详情里下载产物，或放宽 Cloud Agent 对仓库的写权限后再试。

### 若跑完仍是空的（排查）

| 检查项 | 怎么做 |
|--------|--------|
| 运行是否成功 | Automations → 该任务 → Runs，是否 Failed |
| 有没有飞书消息 | 目标群是否收到机器人消息 |
| Webhook | Instructions 文末是否有正确的 `FEISHU_WEBHOOK_URL` |
| Shell | **不用找**：Cloud Agent 自带终端；Tools 菜单里没有 Shell 选项 |
| 是否误开 PR | 关掉 Create pull request |
| 提示词是否最新 | push 最新 `prompt-*.md` 后，把 Instructions 再粘贴一遍（含密钥） |
| 仓库/分支是否选对 | 必须是你的 `invest-agent` 的 `main` |
| A股持仓是否为空 | 确认已 push `data/raw/trades/` |

改完提示词后：**先 push 到 main**，再在 Automations 里把 Instructions 更新成最新内容，然后 **再点一次立即运行**。

确认：

- 美股盘前：仓库有 `premarket-YYYY-MM-DD.md`；飞书为短摘要
- A股盘前：飞书含市场状态 / 仓位建议 / 持仓态度 / **今日应对** 要点；全文在仓库
- 缺数据应写「未获取」/「暂无可靠数据」，未明显编造

---

## 第 6 步：观察一周成本

- 看 [Usage](https://cursor.com/dashboard/usage)
- 目标：两项合计大约 **$15–30/月**（Composer；美股盘前为短任务）
- 偏贵 → 换更便宜模型、缩短提示词、减少搜索次数

---

## 暂不要开

美股收盘日报、财经日报、周报、月报、选题、抄底信号 —— 已在 `scheduler/rules.md` 标为 ⏸，等成本可接受或 A' 稳定再加。
