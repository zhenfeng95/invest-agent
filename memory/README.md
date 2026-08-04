# memory/ — 结构化投研记忆

| 文件 | 用途 |
|------|------|
| `working.json` | 当前关注、在研课题、近期决策、市场环境、`soul_updates` 变更日志 |
| `episodes.json` | 重要对话摘要、关键投资决策及理由、预测与复盘 |

长期对话细节由 claude-mem（若已安装）自动管理；本目录只存投研专用结构化记忆。

## working.json 字段说明

- `current_focus`: 当前关注标的列表
- `active_research`: 在研课题
- `recent_decisions`: 近期决策摘要
- `market_regime`: 权益 / 加密 / 宏观环境判断
- `open_questions`: 待验证问题
- `soul_updates`: `{ "updated_at", "changes", "reason" }[]`

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
