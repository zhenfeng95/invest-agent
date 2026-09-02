# 周度回顾（策略模板 · 自动化）

> **状态**：✅ Automations（周日 10:00）· 骨架对齐月度 · 省 token  
> **Automation 提示词**：`scheduler/prompt-weekly-review.md`  
> **输出**：`output/reviews/weekly/weekly-YYYY-MM-NW.md`（例：`weekly-2026-09-1W.md`）

---

## 命名

| 规则 | 说明 |
|------|------|
| 格式 | `weekly-YYYY-MM-NW.md` |
| 归属月 | 复盘周 **周日** 所在月 |
| N | `ceil(周日日号/7)` → `1W`…`5W`，**每月从 1W 重计** |

---

## 自动化怎么跑

| 项 | 值 |
|----|-----|
| Cron（北京） | `0 10 * * 0` |
| 日报 | **禁止通读**；仅 `rg` 成交日±1 的 §1/§5/§7 |
| 飞书标题 | `周度回顾 YYYY-MM-NW` |
| 上手 | `SETUP-A-prime.md` → Automation ② |

---

## 手动补跑

```text
按 templates/weekly-review.md 生成 2026年9月第1W 周度回顾，保存到 output/reviews/weekly/weekly-2026-09-1W.md
```

---

## 正文骨架（与月度对齐）

```markdown
# YYYY年M月第NW 周度回顾
## 0. 一句话结论
## 1. 整体盈亏
## 2. A股已平仓明细
## 3. 未按信号 / 未守纪律
## 4. 做得好的地方（保留）
## 5. 下周可执行改进
## 6. 原始数据索引
## 7. 月度复盘摘录
```

月度任务只读复盘月的 `weekly-YYYY-MM-*W.md` 的 §7。改 prompt 后须 **重贴** Instructions。
