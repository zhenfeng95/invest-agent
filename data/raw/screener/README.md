# screener/（已停用用户第一层投喂）

第一层改由 Agent / `tools/mtd_screener.py` 全自动跑公式池。

日常默认：

```bash
.venv/bin/python tools/mtd_screener.py --workers 8 --mainline-top 8
```

- **落盘** `output/screener/mtd-screener-*.csv`：仅公式一层
- **二筛**（主线∩四选一）：打印到 stdout，写入收盘日报 **§15.6「明日值得关注的个股」**；默认不写 `*-buysetup.*`

`--write-buysetup` / `--from-pool` / `--refine-only` 仅调试用。
