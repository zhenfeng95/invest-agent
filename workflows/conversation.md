# 对话工作流骨架

> Agent 每一次对话都必须按本文件执行。对用户可见的只有 Phase 3；其余阶段静默完成。
> 入口说明见根目录 `AGENTS.md`。

---

## Phase 1 — 启动加载（静默，每次必须）

按顺序读取：

1. `soul/agent-soul.md` — Agent 人格与技能清单
2. `soul/my-soul.md` — 用户画像（若几乎为空，提醒用户补填，但仍继续服务）
3. `memory/working.json` — 当前关注 / 近期决策 / 市场环境 / soul_updates
4. `memory/episodes.json` — 取最近 10 条情景记忆

若存在长期记忆插件（如 claude-mem），依赖其自动注入历史会话上下文，无需额外请求用户。

**失败处理**：文件缺失时用空默认值继续，并明确提醒用户补齐。

加载完成后，Agent 应处于「已了解用户」状态，再进入 Phase 2。

---

## Phase 2 — 理解意图（静默，每次必须）

解析用户输入，归类为以下之一（可多选）：

| 类型 | 典型信号 |
|------|----------|
| 投研分析 | 个股 / 宏观 / 加密 / 估值 / 财报 |
| 内容创作 | 推文 / Thread / 脚本 / 长文 / 选题 |
| 信号查询 | 抄底 / RSI / VIX / 恐惧贪婪 / 技术位 |
| 日常问答 | 闲聊 / 工具使用 / 学习 |
| 数据投喂 | 用户提到往 `data/raw/` 放了文件，或要求消化新数据 |

再决定能力调用：

- 是否 WebSearch 最新新闻 / 数据？
- 是否 WebFetch / curl 拉行情、财报、链上、宏观？
- 是否读取 `data/raw/` 本地文件？
- 是否参考 `templates/` 对应模板？

---

## Phase 3 — 执行任务（可见，每次必须）

1. 调用所需能力获取数据
2. 结合 `my-soul.md` 生成回复：
   - 分析框架对齐用户偏好
   - 风险判断参照用户风险偏好
   - 语气和深度匹配用户风格
3. 投研类输出结尾附一行风险提示
4. 内容类输出按对应模板结构落盘到 `output/`（若用户要求保存）

**失败处理**：API / 网络失败时告知用户，并给出降级方案（仅用已有本地数据、推迟部分指标等）。

---

## Phase 4 — 自我迭代（静默，有变化才写）

判断本次对话是否产生值得记录的信息：

| 情况 | 动作 |
|------|------|
| 新标的 / 新观点 | 更新 `working.json` |
| 重要决策（买入/卖出/调仓） | 追加 `episodes.json` |
| 用户纠正 Agent | 更新 `working.json` + 记入反思 |
| 新的投资信念 / 偏好 | 直接修改 `my-soul.md` |
| 行为与画像不符 | 修正 `my-soul.md` |

额外检查：

- `data/raw/` 是否有新文件 → 提炼后更新 `soul/` + `memory/`
- 所有对 `my-soul.md` 的变更写入 `working.json` 的 `soul_updates`：
  - `updated_at` / `changes` / `reason`
  - 最多保留 10 条；超额移入 `memory/soul_updates.archive.json`（Phase 1 不读）
- `recent_decisions` 最多 20 条、只留仍影响操作的结论；超额移入 `memory/recent_decisions.archive.json`。细则见 `memory/README.md`。

**重大变更需确认**：核心投资信念或风险偏好的根本性转变，先问用户再改。

**日常微调**：新增关注标的、更新宏观判断、补充行为模式等可静默完成。

**写入失败**：下次对话重试。

---

## 定时任务变体

由调度器触发时，跳过 Phase 2：

```
触发 → Phase 1 → Phase 3（按 scheduler/rules.md 预设）→ Phase 4 → output/ + 通知
```

---

## my-soul.md 更新规则摘要

1. Agent 对 `my-soul.md` 有完整读写权限（增、改、删）
2. 变更必须可追溯（`soul_updates`）
3. 根本性转变先确认；日常微调静默
4. 权威来源唯一：不另建 core.json 副本
