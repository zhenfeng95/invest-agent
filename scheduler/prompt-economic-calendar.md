# 财经日历刷新（Cursor Automation · Agent 只跑脚本）

> 用途：刷新 `data/public/economic-calendar.json` 供个人站展示。  
> **执行器**：Cursor Automations（Cloud Agent）。  
> **数据路径**：Agent **只**跑仓库脚本拉金十（脚本内 HTTP MCP）；**禁止**在对话里调 `list_calendar` / 读 JSON 全文（否则单次数万 token）。

---

你是仓库里的无脑执行器。跳过投研 Phase 1（不要读 soul/memory）。只做下面步骤，完成后用一两句汇报 `count`、是否有变更、是否已进 main。

## 密钥（勿提交仓库；仅存在本 Automation）

```text
JIN10_BEARER_TOKEN=在此粘贴你的金十MCP_Token
```

（若 Dashboard Secrets 已注入同名变量，可省略上面赋值，但仍须能在 shell 里读到。）

## 步骤

1. 导出密钥到当前 shell（若 Instructions 文末已写 `JIN10_BEARER_TOKEN=...`）：
   ```bash
   export JIN10_BEARER_TOKEN  # 或从文末行解析后 export
   ```
   没有 Token → 失败退出，勿编造数据。
2. **先对齐远端，避免工作分支缺脚本**（Cloud Agent 常从旧 tip 起分支）：
   ```bash
   git fetch origin main
   test -f tools/jin10_economic_calendar.py || git checkout origin/main -- tools/jin10_economic_calendar.py
   ```
3. 在仓库根目录执行（**唯一**数据动作）：
   ```bash
   python3 tools/jin10_economic_calendar.py --commit --push
   ```
4. 若当前分支不是 `main` / `master`：
   ```bash
   bash scheduler/merge_to_main.sh
   ```
   `economic-calendar.json` 合并冲突时：保留**本分支/较新**的整文件（以脚本刚写出的为准），不要手工改字段。
5. **禁止**：WebSearch、飞书、读 `economic-calendar.json` 全文、调 jin10 MCP 工具、改其它文件、开 PR。
6. 脚本失败则原样报告 stderr；最多再试 1 次；仍失败则停。
