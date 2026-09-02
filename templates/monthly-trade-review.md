# 月度交易复盘（策略模板 · 自动化）

> **状态**：✅ 挂 Cursor Automations（每月 1 日 10:00 自动复盘上月）  
> **Automation 提示词**：`scheduler/prompt-monthly-trade-review.md`  
> **范本**：`output/reviews/monthly/monthly-2026-08.md`（2026-08 首版）  
> **输出**：`output/reviews/monthly/monthly-YYYY-MM.md`

---

## 自动化怎么跑

| 项 | 值 |
|----|-----|
| Cron（北京） | `0 10 1 * *`（每月 1 日 10:00） |
| 复盘范围 | **上一自然月**（例：10/1 跑 → 复盘 9 月） |
| 飞书标题 | `月度交易复盘 YYYY-MM` |
| 上手 | `scheduler/SETUP-A-prime.md` → Automation ③ |

**前置**：复盘月成交写入 `data/raw/trades/trades-YYYY-MM.csv`。缺文件 Automation 仍会生成复盘并注明「无成交」。

---

## 仍可在对话里手动补跑

Automation 漏跑、或想提前复盘当月时，在对话框发：

```text
按 templates/monthly-trade-review.md 生成 2026年9月交易复盘，保存到 output/reviews/monthly/monthly-2026-09.md
```

或对照范本：

```text
参照 output/reviews/monthly/monthly-2026-08.md 的结构和口径，复盘 9 月份 A股+美股交易；写入 output/reviews/monthly/monthly-2026-09.md
```

---

## Agent 执行清单（必须按序）

1. **Phase 1**：读 `soul/agent-soul.md`、`soul/my-soul.md`、`memory/working.json`、`memory/episodes.json`（近 10）
2. **读成交**：`data/raw/trades/trades-YYYY-MM.csv`（目标月）；缺文件则注明并继续
3. **读快照**：该月末 `positions-YYYY-MM-DD.json`（尽量取月末最后一份）；与 CSV 冲突时 **以 CSV + 最新口述为准** 并注明
4. **对照纪律 / 信号**：
   - GY：五选一买点、距 MA5≤3%、破 MA5/趋势线止损、单票~5%、只建一次、上证线上线下仓位
   - YH：尾盘风格；止损细则待补 → 复盘时标注，不擅自套 GY 硬止损；仍评「追加速 / 非主线」
   - HT：指数仓，不套五选一
   - 美股：VOO/QQQ/IBIT 网格（约 $5）、DCA 信念、机动仓是否无规则
   - 交叉：当日/次日 `output/daily/ashare-close-*.md`（及可用美股日报）里的命中表、破位提醒、账户重心
5. **算账**：
   - 分账户 FIFO 已实现（A：GY/YH/HT；美：US）
   - 胜率、最大亏单
   - 月末未平仓浮盈（标注来源与置信度：高/中/低）
   - **未计佣金/印花税**，文首写明
6. **写文件**：结构对齐下方「正文骨架」→ `output/reviews/monthly/monthly-YYYY-MM.md`
7. **Automation 收尾**：commit → `merge_to_main.sh` → 飞书（手动触发可跳过）
8. **Phase 4**：更新 `memory/working.json` + `episodes.json` 一条 review

---

## 正文骨架（与 8 月范本一致）

```markdown
# YYYY年M月交易复盘

> 生成日期 · 范围 · 数据源 · 口径（FIFO / 未计费 / 置信度）

## 0. 一句话结论
（胜率 vs 盈亏是否背离；下月优先修 1～2 条）

## 1. 整体盈亏
- A / 美 已实现 + 含浮盈估
- 分账户（GY/YH/HT）
- 美股分 ticker 已实现表
- 月末浮盈参考表

## 2. A股已平仓明细
（平仓日 / 账户 / 标的 / 买→卖 / 盈亏 / % / 纪律点评）

## 3. 未按信号 / 未守纪律
分 **高 / 中 / 低**；写清日期、ticker、违反哪条 my-soul 规则

## 4. 做得好的地方（保留）

## 5. 下月可执行改进
（3～5 条，可执行，非鸡汤）

## 6. 原始数据索引
（CSV / positions / 关键日报）

风险提示 + 署名「势能复盘」
```

---

## 硬规则

- 事实 / 解读分开；不编造成交与价格；查不到标「未获取」
- ticker 大写；三账户 **分列** 盈亏，禁止捏成一个「A股总仓%」硬套 GY 规则
- 对标范本深度：既要数字，也要「哪些没按信号 / 没守纪律」
- 改 Automation 行为时同步改 `scheduler/prompt-monthly-trade-review.md` 并重贴 Instructions
