---
name: precheck-before-release
description: 提测前预检：开发自测完成、正式提测之前，对照测试用例逐条检查本次 Git 代码变更的实现情况，输出带代码证据的 Markdown 预检报告。触发场景：用户要求"对照测试用例检查代码变更""提测前检查""用例与实现一致性检查""git diff 预检""开发说功能基本完成但测试用例还没跑"等。支持三种对比模式（工作区/PR三点/仅暂存区）与五档判定（已覆盖/部分覆盖/未实现/存在偏差/无法判定）。
---

# 提测前预检（Precheck Before Release）

## 定位

这是一次**面向业务规则的静态一致性预检**，不是代码覆盖率检查。它回答的问题是：
"测试用例中描述的功能、业务规则和异常处理，能否在本次代码变更中找到对应实现？"

适合在**开发自测完成、正式提测之前**执行。价值是把一部分原本到提测后（冒烟阶段）才暴露的
"用例与实现不一致"问题提前发现，减少重复沟通、打回与等待修复。

## 工作流

1. **收集变更**：`scripts/collect_diff.py` 获取 Git 差异 → `diff.json`
2. **解析用例**：`scripts/parse_cases.py` 读取用例文件（xlsx/csv/md）→ `cases.json`
3. **逐条关联**：`scripts/analyze.py` 按规则关键词产出五档判定**草稿** → `analysis.json`
4. **AI 复核（必须）**：AI 结合 `diff.json` 的 diff 原文复核每条草稿，重点修正
   「无法判定 / 未实现 / 存在偏差」，直接编辑 `analysis.json` 中的 status/reason/missing。
5. **生成报告**：`scripts/report.py` 由复核后的 analysis.json 生成 Markdown 报告。

## 快速开始

```bash
bash scripts/run_precheck.sh \
  --repo <仓库路径> \
  --mode pr \
  --base prod_1.0.0 \
  --feature feat_tenant_lease \
  --cases <用例文件.xlsx> \
  --outdir ./precheck_out
```

产物（位于 `--outdir`）：
- `diff.json` 变更结构化数据（含 diff 原文，供 AI 复核）
- `cases.json` 结构化用例
- `analysis.json` 逐条判定草稿
- `precheck_report.md` 报告

**AI 复核后定稿**：编辑 `analysis.json`（status/reason/missing），再执行
`python3 scripts/report.py --analysis <analysis.json> --out <报告路径.md>`。

## 三种对比模式（--mode）

| 模式 | 适用阶段 | 对比范围 | 命令 |
| --- | --- | --- | --- |
| `worktree` | 日常开发（未整理提交） | 工作区全部改动（已暂存+未暂存+未跟踪） | `--mode worktree` |
| `pr` | 合入评审（PR/MR） | `base...feature` 三点语法，近似真实 PR 变更范围 | `--mode pr --base B --feature F` |
| `staged` | 提交前自检 | 仅 `git add` 的内容 | `--mode staged` |

> 主分支频繁合并时优先用 `pr` 模式的三点语法（`git diff base...feature`），
> 从共同祖先开始比较，减少基准分支后续提交对变更范围的干扰。

## 判定维度（五档）

- **已覆盖**：变更中找到了与用例预期一致的实现，关键条件基本完整。
- **部分覆盖**：主流程已实现，但边界、异常、权限或状态处理不完整。
- **未实现**：当前变更范围内没有找到对应代码。
- **存在偏差**：代码已有实现，但规则、字段、返回结果或流程与用例不一致（含 TODO/占位）。
- **无法判定**：仅凭静态代码和当前材料不足以得出结论（配置中心、公共组件、运行时行为）。

**「无法判定」不是无效结果**，应单独列出并要求人工确认，不要强行给出"已实现/未实现"。

## AI 复核要点

`analyze.py` 的输出是**草稿**。AI 复核时必须：
1. 读取 `diff.json` 的 diff 原文，对照每条用例的命中行确认规则是否真实一致（警惕关键词误命中，
   例如日期比较行被金额/范围关键词命中）。
2. 命中行与用例无关时，改判为「未实现」并写明依据。
3. 校验逻辑位于未变更的公共模块/配置中心/运行时行为时，改判为「无法判定」并注明依赖位置。
4. 主流程完整但边界不完整（如仅拦截部分状态）时，改判为「部分覆盖」。
5. 代码中只有 TODO/占位标记时，保持「存在偏差」。
6. 改判后更新 `analysis.json` 的 status/reason/missing/suggestion，再重新生成报告。

## 报告解读

- **整体分布**：快速判断是否具备提测条件；「未实现/存在偏差」先与开发确认，不要当质量结论直接用。
- **高风险缺口**：优先处理阻塞主流程、影响数据正确性的缺口，分批同步开发，提高沟通效率。
- **逐条证据**：每条结论含关联文件、代码位置、已找到实现、缺少/不一致、建议处理方向；
  开发可据此快速判断结论是否成立，测试可据此调整冒烟重点。

## 脚本说明

| 脚本 | 输入 | 输出 | 说明 |
| --- | --- | --- | --- |
| `collect_diff.py` | --repo --mode [--base --feature] | diff.json | 收集三种范围的 Git 变更 |
| `parse_cases.py` | --file（xlsx/csv/md） | cases.json | 解析用例（表头自动模糊匹配） |
| `analyze.py` | --diff --cases | analysis.json | 规则关键词关联，产出五档判定草稿 |
| `report.py` | --analysis | 报告.md | 生成 Markdown 报告 |
| `run_precheck.sh` | 见快速开始 | 全部产物 | 一键串联 1-2-3-5 |

## 注意事项

- 静态预检**查不到运行时行为**（配置中心、动态规则、真实服务响应），这类条目应标「无法判定」。
- 判定质量高度依赖用例质量：用例写得越具体（明确规则、边界、异常、字段），结论越可靠。
- 本 Skill 不替代代码评审与测试执行，只负责提前暴露一部分问题。
- xlsx 解析需要 `openpyxl`（`pip install openpyxl`）；csv 需 UTF-8 编码。
