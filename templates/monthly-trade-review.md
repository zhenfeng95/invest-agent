# 月度交易复盘（策略模板 · 自动化）

> **状态**：✅ Automations（每月 1 日 10:00）· 主读周报 §7 · 禁止通读日报  
> **Automation 提示词**：`scheduler/prompt-monthly-trade-review.md`  
> **范本**：`output/reviews/monthly/monthly-2026-08.md`  
> **输出**：`output/reviews/monthly/monthly-YYYY-MM.md`

---

## 自动化怎么跑

| 项 | 值 |
|----|-----|
| Cron（北京） | `0 10 1 * *` |
| 复盘范围 | **上一自然月** |
| 主数据 | 当月 CSV + 月末 positions + `weekly-{月}-*W.md` 的 **§7** |
| 禁止 | 任何 `ashare-close` / `us-close` |
| 飞书标题 | `月度交易复盘 YYYY-MM` |
| 上手 | `SETUP-A-prime.md` → Automation ③ |

**前置**：复盘月 CSV；尽量当月周报齐全。缺周报则该周纪律标「未审计」，仍不读日报。

---

## 手动补跑

```text
按 templates/monthly-trade-review.md 生成 2026年9月交易复盘，保存到 output/reviews/monthly/monthly-2026-09.md
```

---

## Agent 执行清单

1. Phase 1：仅 `my-soul` + memory 短读
2. CSV（账本权威）+ 月末 positions
3. rg 各 `weekly-{复盘月}-*W.md` 的 `## 7. 月度复盘摘录`
4. FIFO 分账户；合并纪律高/中/低
5. 写 `monthly-YYYY-MM.md` → commit → merge → 飞书
6. Phase 4 短更新

---

## 正文骨架（与 8 月范本一致）

```markdown
# YYYY年M月交易复盘
## 0. 一句话结论
## 1. 整体盈亏
## 2. A股已平仓明细
## 3. 未按信号 / 未守纪律
## 4. 做得好的地方（保留）
## 5. 下月可执行改进
## 6. 原始数据索引（含所用 weekly 列表；注明未读 ashare-close）
```

---

## 硬规则

- 盈亏只信 CSV；信号/破位证据只信周报 §7
- 三账户分列；不编造；缺证据标置信度
- 改 prompt 后须 **重贴** Automations Instructions
