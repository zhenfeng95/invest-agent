# 周度回顾（策略模板 · 自动化）

> **状态**：✅ 挂 Cursor Automations（每周日 10:00 自动复盘当周）  
> **Automation 提示词**：`scheduler/prompt-weekly-review.md`  
> **输出**：`output/reviews/weekly/weekly-YYYY-Www.md`

---

## 自动化怎么跑

| 项 | 值 |
|----|-----|
| Cron（北京） | `0 10 * * 0`（每周日 10:00） |
| 复盘范围 | **刚结束的自然周**（ISO 周号 `YYYY-Www`） |
| 飞书标题 | `周度回顾 YYYY-Www` |
| 上手 | `scheduler/SETUP-A-prime.md` → Automation ② |

**前置**：当周成交写入 `data/raw/trades/trades-YYYY-MM.csv`；A股收盘日报正常产出。缺文件 Automation 仍会生成回顾并注明「无成交」。

---

## 仍可在对话里手动补跑

Automation 漏跑、或想提前复盘当周时，在对话框发：

```text
按 templates/weekly-review.md 生成 2026-W36 周度回顾，保存到 output/reviews/weekly/weekly-2026-W36.md
```

或：

```text
参照 scheduler/prompt-weekly-review.md 的结构和口径，复盘本周 A股+美股组合表现；写入 output/reviews/weekly/
```

---

## Agent 执行清单（必须按序）

### Phase 1 · 加载

1. `soul/agent-soul.md`、`soul/my-soul.md`
2. `memory/working.json`、`memory/episodes.json`（最近 10 条）

### Phase 3 · 数据

1. 复盘周成交（从当月 CSV 筛选）
2. 周末 `positions-*.json`
3. 复盘周内全部 `ashare-close-*.md`（+ 可选 `us-close-*.md`）
4. 周初/周末参考价（日报或搜索）

### Phase 3 · 输出

连续 §0–§6（见 prompt）；全文 800～1500 字；比月度复盘短。

### Phase 4 · 记忆

更新 `working.json` + `episodes.json`（`type: weekly_review`）。

---

## 与月度复盘的分工

| 维度 | 周度回顾 | 月度交易复盘 |
|------|----------|--------------|
| 频率 | 每周日 | 每月 1 日 |
| 深度 | 轻量 highlights | FIFO 逐笔 + 纪律审计 |
| 算账 | 周汇总 + 浮盈变化 | 完整已实现 + 胜率 |
| 输出 | `output/reviews/weekly/` | `output/reviews/monthly/` |
