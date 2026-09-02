# 周度回顾（策略模板 · 自动化）

> **状态**：✅ Automations（周日 10:00）· 骨架对齐月度 · 省 token  
> **Automation 提示词**：`scheduler/prompt-weekly-review.md`  
> **输出**：`output/reviews/weekly/weekly-YYYY-Www.md`

---

## 自动化怎么跑

| 项 | 值 |
|----|-----|
| Cron（北京） | `0 10 * * 0` |
| 复盘范围 | 刚结束 ISO 周 |
| 日报 | **禁止通读**；仅 `rg` 成交日±1 的 §1/§5/§7 |
| 飞书标题 | `周度回顾 YYYY-Www` |
| 上手 | `SETUP-A-prime.md` → Automation ② |

**前置**：成交入 CSV。缺文件仍出回顾。

---

## 手动补跑

```text
按 templates/weekly-review.md / scheduler/prompt-weekly-review.md 生成 2026-W36 周度回顾，保存到 output/reviews/weekly/weekly-2026-W36.md
```

---

## 正文骨架（与月度对齐）

```markdown
# YYYY-Www 周度回顾
## 0. 一句话结论
## 1. 整体盈亏
## 2. A股已平仓明细
## 3. 未按信号 / 未守纪律
## 4. 做得好的地方（保留）
## 5. 下周可执行改进
## 6. 原始数据索引
## 7. 月度复盘摘录   ← 月初月度任务只读本节
```

---

## 与月度分工

| | 周度 | 月度 |
|--|------|------|
| 读日报 | 薄读（rg） | **不读** |
| 读周报 | — | 只读各周 §7 |
| 账本 | 本周汇总 | 月 CSV FIFO |
| 输出 | `reviews/weekly/` | `reviews/monthly/` |

改行为须同步改 prompt 并 **重贴** Automations Instructions。
