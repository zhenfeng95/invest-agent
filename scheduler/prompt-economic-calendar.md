# 财经日历刷新（方案 2 · 脚本直连，禁止读日历进上下文）

> 用途：刷新 `data/public/economic-calendar.json` 供个人站展示。  
> **不要**走投研 Phase 1 加载 soul/memory；**不要**调用金十 MCP 工具把日历贴进对话。  
> 本提示词仅在「无法本机 cron、只能用 Cloud Agent」时使用；优先本机 `scheduler/run-economic-calendar.sh`。

---

你是仓库里的无脑执行器。只做下面步骤，完成后用一两句汇报 `count` 与是否 push 成功。

1. 确认环境有 `JIN10_BEARER_TOKEN`（Secrets / env）。没有则失败退出，勿编造数据。
2. 在仓库根目录执行（**唯一**数据动作）：
   ```bash
   python3 tools/jin10_economic_calendar.py --commit --push
   ```
   若当前不在 `main`，写完后执行：`bash scheduler/merge_to_main.sh`
3. **禁止**：WebSearch、读 `economic-calendar.json` 全文、调 jin10 MCP `list_calendar`、改其它文件、飞书推送。
4. 脚本已失败则原样报告 stderr，不要重试超过 1 次。
