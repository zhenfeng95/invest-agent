# screener/ — 用户第一层选股池

第一层选股由你完成；Agent **不代选**。

## 用法

1. 把当日一层池写成 CSV（或对话里指定其他路径）：

```csv
code,name
300827,上能电气
002150,正泰电源
```

默认路径：`data/raw/screener/pool-latest.csv`

2. 收盘日报前置会跑：

```bash
.venv/bin/python tools/mtd_screener.py --workers 8
# 或：.venv/bin/python tools/mtd_screener.py --from-pool <你的文件>
```

3. 结果写入日报 **§15.6「明日值得关注的个股」**：
   - **命中四选一**表
   - **未命中**表  
   表头：代码、简称、买点、收盘、MA5、ext、V、MA(V,5)、VR、换手%

未交池 / 文件为空 → §15.6 写「用户未提供一层池」。

`--formula` 为可选调试（全市场月初至今公式），**不是**收盘日报默认。
