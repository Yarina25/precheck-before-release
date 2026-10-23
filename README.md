# 提测前预检 Skill（precheck-before-release）部署说明

将本压缩包解压到 `D:\projects` 后，目录结构如下：

```
D:\projects\
├── precheck-before-release\          # Skill 本体
│   ├── SKILL.md                      # Skill 定义与使用说明
│   └── scripts\
│       ├── run_precheck.sh           # 一键预检（Git Bash 下运行）
│       ├── collect_diff.py           # 收集 Git 变更（三种模式）
│       ├── parse_cases.py            # 解析测试用例（xlsx/csv/md）
│       ├── analyze.py                # 逐条关联，产出五档判定草稿
│       └── report.py                 # 生成 Markdown 预检报告
└── demo_precheck\                    # 演示工程（可复现）
    ├── demo_setup.sh                 # 一键重建演示仓库与用例
    ├── repo\                         # 演示 git 仓库（prod_1.0.0 / feat_tenant_lease）
    ├── cases\lease_cases.xlsx        # 10 条租赁合同用例
    └── out\                          # 预检产物（含最终报告）
```

## 环境要求（Windows）

- Windows 10/11，安装 **Python 3.9+** 与 **Git**
- 安装依赖：`pip install openpyxl`
- 一键脚本 `run_precheck.sh` 请在 **Git Bash** 中运行；CMD/PowerShell 可直接分步调用 python 脚本

## 快速开始

方式一：Git Bash 一键预检

```bash
cd /d/projects
bash precheck-before-release/scripts/run_precheck.sh \
  --repo <你的仓库路径> \
  --mode pr \
  --base prod_1.0.0 \
  --feature feat_tenant_lease \
  --cases <用例文件.xlsx> \
  --outdir ./precheck_out
```

方式二：CMD/PowerShell 分步执行

```bat
python precheck-before-release\scripts\collect_diff.py --repo <仓库> --mode pr --base prod_1.0.0 --feature feat_tenant_lease --out diff.json
python precheck-before-release\scripts\parse_cases.py --file cases.xlsx --out cases.json
python precheck-before-release\scripts\analyze.py --diff diff.json --cases cases.json --out analysis.json
python precheck-before-release\scripts\report.py --analysis analysis.json --out precheck_report.md
```

产物：`diff.json`（变更+diff 原文）、`cases.json`（结构化用例）、`analysis.json`（判定草稿）、`precheck_report.md`（报告）。

## 三种对比模式（--mode）

| 模式 | 适用阶段 | 对比范围 |
| --- | --- | --- |
| `worktree` | 日常开发 | 工作区全部改动（已暂存+未暂存+未跟踪） |
| `pr` | 合入评审 | `base...feature` 三点语法，近似真实 PR 变更范围 |
| `staged` | 提交前自检 | 仅 `git add` 的内容 |

## 判定维度（五档）

- **已覆盖**：变更中找到了与用例预期一致的实现，关键条件基本完整。
- **部分覆盖**：主流程已实现，但边界、异常、权限或状态处理不完整。
- **未实现**：当前变更范围内没有找到对应代码。
- **存在偏差**：代码已有实现，但规则/字段/返回结果/流程与用例不一致（含 TODO/占位）。
- **无法判定**：静态代码与当前材料不足以得出结论（配置中心、公共组件、运行时行为），需人工确认。

**重要**：`analyze.py` 输出的是**草稿**，需由 AI（或人工）结合 `diff.json` 的 diff 原文复核
「无法判定/未实现/存在偏差」条目，修正 `analysis.json` 后重新运行 `report.py` 定稿。
脚本是规则关键词驱动的确定性工具，语义判断（阈值一致、边界完整、公共模块依赖）必须经过复核。

## 演示复现

Git Bash 下执行：

```bash
cd /d/projects
bash demo_precheck/demo_setup.sh     # 重建演示仓库 + 用例
bash precheck-before-release/scripts/run_precheck.sh \
  --repo ./demo_precheck/repo --mode pr \
  --base prod_1.0.0 --feature feat_tenant_lease \
  --cases ./demo_precheck/cases/lease_cases.xlsx --outdir ./demo_precheck/out
```

演示结论（10 条用例）：已覆盖 4 / 部分覆盖 2 / 未实现 1 / 存在偏差 1 / 无法判定 2。
