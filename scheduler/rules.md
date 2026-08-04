# 当前启用方案：A'（Cursor Automations）

> 低成本起步：只跑 **2 个** Automation。其余任务写在下方全文规则中，暂不启用。
> 执行器：**Cursor Automations（Cloud Agent）**，不再依赖 Claude Code scheduler。

| Automation | Cron（北京时间） | 说明 |
|------------|------------------|------|
| **① 盘前提醒** | `0 21 * * 1-5` | 工作日 21:00 |
| **② 合并抄底信号** | `0 9 * * *` | 每天 09:00，一次跑完 S&P 500 + BTC |

提示词见同目录：
- `prompt-premarket.md`
- `prompt-signals.md`

月成本粗估约 **$15–30**（视模型而定）；务必在 Cursor Dashboard 设消费上限。

---

# 定时任务规则（完整清单）

> 所有时间均基于北京时间（UTC+8）。
> 本文件是规则的权威来源；改规则后请同步改 Automations。

## 每日任务

### 财经日报（每日 08:00）— 暂未启用
- cron: `0 8 * * *`
- 执行：读取 soul/ 和 memory/ 上下文，用 WebSearch 搜索隔夜市场新闻，用 WebFetch 调 API 拉取行情数据，按 `templates/daily-brief.md` 生成日报，保存到 `output/daily/YYYY-MM-DD.md` 并推送通知
- 模板要点：

```
# 财经日报 — YYYY-MM-DD

## 隔夜美股
- 三大指数收盘：道指 / 标普 / 纳指（涨跌幅）
- 持仓标的表现：[自动读取 my-soul.md 持仓列表]
- 盘后重要异动

## 加密市场
- BTC / ETH 24h 表现
- BTC ETF 净流入/流出
- 恐惧贪婪指数

## 宏观要闻
- 今日重要经济数据（CPI/PPI/非农/Fed讲话等）
- 政策动态（关税、监管、地缘）

## 信号面板
- S&P 500 抄底信号：[触发/未触发]（附关键指标值）
- BTC 抄底信号：[触发/未触发]（附关键指标值）

## 今日关注
- 1-2 句核心判断/提醒
```

### 盘前提醒（每日 21:00 / 美东 9:00）— ✅ A' 启用
- cron: `0 21 * * 1-5`
- 执行：检查以下事项并推送简短提醒
  - 今日是否有持仓标的财报发布
  - 是否有重要经济数据公布
  - 期权到期日提醒（如适用）
  - 关键技术位提醒（如某标的接近支撑/阻力位）
- 输出：`output/daily/premarket-YYYY-MM-DD.md`（或直接推送短消息）
- 提示词：`scheduler/prompt-premarket.md`

## 信号系统

### 合并抄底信号（每日 09:00）— ✅ A' 启用（SPX + BTC 一次跑完）
- cron: `0 9 * * *`
- 提示词：`scheduler/prompt-signals.md`
- 输出：
  - `output/signals/spx-YYYY-MM-DD.md`（仅触发时，或每日简要记录）
  - `output/signals/btc-YYYY-MM-DD.md`
  - 可选汇总：`output/signals/daily-YYYY-MM-DD.md`

### 美股抄底信号（S&P 500）规则
- 规则：满足 3/5 项触发「关注」，4/5 项触发「考虑建仓」

| 指标 | 触发条件 | 权重 |
|------|---------|------|
| VIX | > 30 | ★★★ |
| S&P 500 RSI(14) | < 30 | ★★★ |
| 距 200 日均线 | 跌破 > 5% | ★★ |
| Put/Call Ratio | > 1.2 | ★★ |
| 恐惧贪婪指数 | < 20（极度恐惧） | ★★ |

- 信号输出格式：

```
🚨 S&P 500 抄底信号 — [关注 / 考虑建仓]
触发指标：VIX XX ✅ | RSI XX ✅ | 200MA -X% ❌ | P/C X.XX ✅ | FGI XX ❌
当前点位：XXXX | 关键支撑位：XXXX / XXXX
历史参考：上次类似信号 YYYY-MM-DD，后续 30 日涨幅 X%（查不到则写「暂无」）
⚠️ 信号仅供参考，不构成投资建议
```

### BTC 抄底信号规则
- 规则：满足 3/5 项触发「关注」，4/5 项触发「考虑建仓」

| 指标 | 触发条件 | 权重 |
|------|---------|------|
| BTC RSI(14) | < 30 | ★★★ |
| MVRV Z-Score | < 0 | ★★★ |
| 加密恐惧贪婪指数 | < 15 | ★★ |
| 交易所 BTC 净流出 | 连续 7 日净流出 | ★★ |
| 资金费率 | 连续 3 日为负 | ★ |

- 触发时保存到 `output/signals/btc-YYYY-MM-DD.md`

## 周度/月度任务 — 暂未启用

### 周度回顾（每周日 10:00）
- cron: `0 10 * * 0`
- 执行：生成持仓组合周度回顾（收益、归因、下周展望），保存到 `output/research/weekly/YYYY-Www.md`

### 月度复盘（每月 1 日 10:00）
- cron: `0 10 1 * *`
- 执行：生成月度投资复盘 + 配置再平衡建议，保存到 `output/research/monthly/YYYY-MM.md`

### 内容选题建议（每周三 10:00）
- cron: `0 10 * * 3`
- 执行：基于本周热点 + 用户关注领域，推荐 3–5 个内容选题，保存到 `output/content/topics-YYYY-MM-DD.md`

## 定时任务工作流

```
Automations 触发 → Phase 1（加载 soul + memory）→ Phase 3（执行预设任务）→ Phase 4（更新记忆）→ 写入 output/
```

## 注册清单

| 任务 | Cron (UTC+8) | 状态 | 输出目录 |
|------|--------------|------|----------|
| 盘前提醒 | `0 21 * * 1-5` | ✅ A' | output/daily/ |
| 合并抄底信号 | `0 9 * * *` | ✅ A' | output/signals/ |
| 财经日报 | `0 8 * * *` | ⏸ 暂缓 | output/daily/ |
| 周度回顾 | `0 10 * * 0` | ⏸ 暂缓 | output/research/weekly/ |
| 月度复盘 | `0 10 1 * *` | ⏸ 暂缓 | output/research/monthly/ |
| 内容选题 | `0 10 * * 3` | ⏸ 暂缓 | output/content/ |
