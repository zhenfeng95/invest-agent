# memory/ — 结构化投研记忆

| 文件 | 用途 |
|------|------|
| `working.json` | **工作记忆（RAM）**：当前关注、在研、近期决策、市况、`soul_updates`。Phase 1 必读。保持短。 |
| `episodes.json` | 重要对话摘要、关键投资决策及理由、预测与复盘（Phase 1 只取最近 10 条） |
| `soul_updates.archive.json` | `my-soul.md` 完整变更历史。Phase 1 **不读**。 |
| `recent_decisions.archive.json` | 已滚出的决策流水。Phase 1 **不读**。日报正文以 `output/daily/` 为准。 |

长期对话细节由 claude-mem（若已安装）自动管理；本目录只存投研专用结构化记忆。

## working.json 字段说明

- `current_focus`: 核心持仓 + 仍在观察（一层池可列入）。**已平仓踢出**。
- `active_research`: 未平仓与仍在跟的课题。已平仓摘要进 `episodes.json` / `data/raw/trades/`，不堆在这里。
- `recent_decisions`: 仍影响操作的结论，最多 **20** 条（新的插最前）。日报「任务完成」类不写入（已有 `output/daily/`）。超额 prepend 进 `recent_decisions.archive.json`。
- `market_regime`: 短快照（持仓一句 + 市况一句）。
- `open_questions`: 未闭环问题；去重；做完即删。
- `soul_updates`: `{ "updated_at", "changes", "reason" }[]`，最多 **10** 条（新的插最前）。超额 prepend 进 `soul_updates.archive.json`。

## 留存规则（写记忆时必须遵守）

1. Phase 1 只读 `working.json`，不读 `*.archive.json`。
2. 追加 `recent_decisions` / `soul_updates` 后若超上限，把最旧条目移到对应 archive 文件顶部（保留 `archived_at` 可选）。
3. 同一结论的迭代只留**最终态**一条（例如日报结构连改五版，working 里只留现行章节）。
4. `open_questions` 禁止重复贴同一条「须重贴 Automations」。

## episodes.json 条目建议字段

```json
{
  "id": "ep-001",
  "date": "2026-08-04",
  "type": "decision|dialogue|prediction|review",
  "summary": "一句话摘要",
  "detail": "可选详情",
  "tickers": ["PLTR"],
  "outcome": null
}
```
