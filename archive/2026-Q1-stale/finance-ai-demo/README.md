# README - 财务 AI Demo 包

## 文件结构

```
finance-ai-demo/
├── demo1_clean_excel/
│   └── messy_expenses.xlsx        # 故意搞乱的报销表
├── demo2_merge_analysis/
│   ├── expenses_2024_01.csv       # 1月费用数据
│   ├── expenses_2024_02.csv       # 2月费用数据
│   └── expenses_2024_03.csv       # 3月费用数据
├── demo3_invoice_extract/
│   └── INV-2024-01xx.txt × 7     # 模拟发票（7张）
├── prompts/
│   ├── demo1_prompt.md            # Demo1 完整 prompt
│   ├── demo2_prompt.md            # Demo2 完整 prompt
│   └── demo3_prompt.md            # Demo3 完整 prompt
└── 演讲脚本.md                    # 30分钟完整脚本
```

## 使用前准备

1. 确认 Claude Code 已安装：`claude --version`
2. 把整个文件夹放到演示用的电脑上
3. 提前跑一遍三个 demo，确认输出正常
4. Demo 时 cd 到对应子目录再输入 prompt

## 顺序建议

Demo1（数据清洗）→ Demo2（合并分析）→ Demo3（发票提取）⭐

Demo3 视觉冲击最强，放压轴。
