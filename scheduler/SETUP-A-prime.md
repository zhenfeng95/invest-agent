# A' 方案上手：仅 A股收盘日报

你已选择 **A'**：只用 Cursor Automations，当前开 **1 个** 定时任务。

**当前组合**：
1. **A股收盘日报**（工作日 **17:00**）— **精简版**：连续 §0–§8（§4=资金与板块共振；见 `prompt-ashare-close-daily.md`；完整版备查 `prompt-ashare-close-daily-origin.md`）

**已暂停 / 停用**：
- **美股收盘日报**（原 08:00）→ Automation「Invest US Close Daily」请 **Pause**
- 美股盘前提醒（原 21:00）→ Automation 请 **Pause**
- A股盘前提醒（原 09:00）→ Automation 请 **Pause**
- 合并抄底信号 → 继续 Pause / 删除

**通知渠道**：**仅飞书**（自定义机器人 Webhook）。不再发邮件 / 不再用 Resend。  
**存档方式**：写入 `output/` → commit → `bash scheduler/merge_to_main.sh`（并进 **main** 并删 `cursor/*`）→ 再发飞书；**不开 PR**。  
**飞书**：`scheduler/feishu_send.py`（表格转条目 + 卡片；超长截断；脚注为 main 上 GitHub 全文链接）。

> 成本提示：仅 A股收盘精简版时月消耗粗估约 **$25–50**（视模型与 Run 次数）；务必设 Dashboard 上限。

---

## 第 1 步：让项目能被云端读到

Cloud Agent 读的是 **GitHub/GitLab 上的仓库**，不是你电脑上未推送的文件。

1. 把本文件夹建成 Git 仓库并推到 GitHub（若还没有）
2. 在 Cursor 连接该仓库（Settings / Cloud Agents / GitHub）
3. 之后改 `soul/`、`scheduler/`、`data/raw/trades/` 要 **commit + push**，云端才会看到最新持仓
4. **权限**：Cloud Agent 必须能 **push `main`** 并删除 `cursor/*` 分支（否则合并脚本会失败）

---

## 第 2 步：打开计费开关

1. 打开 [cursor.com/dashboard](https://cursor.com/dashboard)
2. 确认至少是 **Pro**
3. 开启 **On-demand usage**，设月消费上限（双收盘建议先 **$60–100**，再按 Usage 调）
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
5. 安全设置：先别开签名；可选「自定义关键词」并设为 `收盘`（则消息正文须含该词）。开了签名要改提示词，跟我说一声

#### 找不到「自定义机器人」时

| 原因 | 怎么办 |
|------|--------|
| 用了手机 / 网页版 | 改用 **PC 客户端** |
| 在单聊 / 会话里找 | 必须进 **群聊** |
| 企业租户关掉了能力 | 换个人号建私人群试；或问管理员是否禁用群自定义机器人 |
| 无添加权限 | 需群主/管理员，或自己建新群 |
| 只看到一堆应用机器人 | 列表顶部或搜索「自定义」；点的是 **添加机器人** 后的弹窗，不是开放平台 |

**不要把 Webhook URL commit 进仓库。**

### 3.2 把 URL 贴进 Automation（不是 IDE 本地 MCP）

每个 Automation 的 Instructions = **对应仓库提示词全文** + 文末密钥段：

```text
## 密钥（勿提交仓库；仅存在本 Automation）
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的token
```

可选：本机自测可把 URL 写进本地 `.env`（已 gitignore），与云端任务互不影响。

### 3.3 可卸掉 Resend

若 Automation Tools 里还挂着 Resend MCP：**删除 / 关掉** 即可，本方案不再需要。

---

## 第 4 步：建 / 改 Automation（共 2 个）

入口任选其一：

- 浏览器：[cursor.com/automations](https://cursor.com/automations)
- 或 Cursor **Agents Window** → Automations
- 或在 Agents Window 里用 `/automate`

### 先 Pause 旧任务

| 旧任务 | 动作 |
|--------|------|
| Invest Premarket Reminder（美股盘前 21:00） | **Pause** |
| Invest A-Share Premarket（A股盘前 09:00） | **Pause** |
| 抄底信号等 | 继续 Pause / 删除 |

### 共用设置

| 项 | 填什么 |
|----|--------|
| 仓库 | `invest-agent` 的 `main` |
| 模型 | Composer 或 Sonnet（收盘日报长，可先 Composer；偏贵再换） |
| Tools | ❌ **不要开** Send to Slack / Teams / Open Pull Request；可选 Memories；飞书靠提示词脚本（Cloud Agent **自带终端**） |
| 通知 | 靠飞书 Webhook |

### Automation ①：A股收盘日报

| 项 | 填什么 |
|----|--------|
| 名称 | Invest A-Share Close Daily |
| 触发 | Cron：`0 17 * * 1-5`（北京时间工作日 **17:00**；错开刚收盘高峰） |
| Instructions | 粘贴 `scheduler/prompt-ashare-close-daily.md`「---」以下内容 + 文末 `FEISHU_WEBHOOK_URL=...`（**须重贴**：含扶摇 MCP 优先 + 同花顺/东财回退；§1 操作提示+账户重心） |

**数据源**：能挂 MCP 时先打扶摇；云端无 MCP / 扶摇失败则按 prompt 内 P1/P2（同花顺网页、东财、本地 tools）写完，勿空等。

**时区提醒**：Cursor cron 若按 UTC：北京 17:00 = UTC `0 9 * * 1-5`。以界面标注为准。

### Automation ②：美股收盘日报 — ⏸ 已暂停

| 项 | 填什么 |
|----|--------|
| 名称 | Invest US Close Daily |
| 触发 | Cron：`0 8 * * 1-5`（历史；工作日 **08:00**） |
| 操作 | 在 Cursor Automations 对该任务点 **Pause**；精简版 `prompt-us-close-daily.md`（§0–§6）；完整版 `prompt-us-close-daily-origin.md` |
| Instructions | 恢复启用时再粘贴「---」以下内容 + 文末 `FEISHU_WEBHOOK_URL=...` |

**时区提醒**（恢复时）：Cursor cron 若按 UTC：北京 08:00 = UTC `0 0 * * 1-5`。

若 Automation 已建过：当前只需 **Pause**；不必删除。

---

## 第 5 步：先手动跑一次

改完 A股收盘提示词后点 **Run now / 立即运行**（验证 A股收盘日报即可；美股收盘已暂停勿跑）。

### 成功时你应该看到什么

1. **飞书群**收到机器人消息（标题含「A股收盘日报」）
2. **Automation 运行详情**：成功；摘要里有文件路径、`merge_to_main` 成功、飞书 `code:0`；**没有**「Opened pull request」
3. **GitHub `main`**：对应 `output/daily/ashare-close-YYYY-MM-DD.md` 出现；若当日交了用户池，`data/raw/screener/pool-latest.csv` 亦应已更新（临时 `cursor/*` 应已删除）
4. 本机：`git pull origin main` 后 `output/` 同步

若飞书没到：核对 Webhook URL → 机器人是否在群里 → 运行日志响应码。

若只有 `cursor/*` 有文件、**main 没有**：合并脚本失败或无 main 写权限——看 `merge_to_main` 日志。

### 若跑完仍是空的（排查）

| 检查项 | 怎么做 |
|--------|--------|
| 运行是否成功 | Automations → Runs，是否 Failed |
| 有没有飞书消息 | 目标群是否收到 |
| Webhook | Instructions 文末是否有正确的 `FEISHU_WEBHOOK_URL` |
| 是否误开 PR | 关掉 Create pull request |
| main 是否有文件 | GitHub 打开 `main` 的 `output/daily/` |
| 提示词是否最新 | push 后把 Instructions 再粘贴一遍（含密钥） |
| 持仓是否为空 | 确认已 push `data/raw/trades/` |

改完提示词后：**先 push 到 main**，再更新 Automations Instructions，然后 **Run now**。

确认：

- 仓库有对应 `*-close-YYYY-MM-DD.md`
- 飞书含大盘 / 板块 / 持仓 / 明日计划等（超长会截断，脚注为 main 上 GitHub 链接）
- 缺数据应写「未获取」/「暂无可靠数据」

---

## 第 6 步：观察成本

- 看 [Usage](https://cursor.com/dashboard/usage)
- 双收盘单次都明显高于盘前；A股已切**精简版**提示词；仍偏贵 → 换更便宜模型
- 需要早盘决策时，再 **Enable** 回 A股盘前（09:00）

---

## 暂不要开

美股盘前、A股盘前、财经日报、周报、月报、选题、抄底信号 —— 已在 `scheduler/rules.md` 标为 ⏸。
