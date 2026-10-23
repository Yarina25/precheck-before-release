#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由 analysis.json 生成 Markdown 预检报告 —— 提测前预检第四步。

用法：
  python3 report.py --analysis analysis.json --out precheck_report.md

报告结构：
  1. 报告说明（定位与限制）
  2. 检查元信息
  3. 整体分布
  4. 高风险缺口（存在偏差 / 未实现 / 部分覆盖 / 无法判定，按风险排序）
  5. 逐条证据（关联文件、代码位置、已找到实现、规则命中、结论依据、建议）
  附：判定维度说明
"""

import argparse
import json

RISK_ORDER = ["存在偏差", "未实现", "部分覆盖", "无法判定", "已覆盖"]

STATUS_LEGEND = {
    "已覆盖": "在变更中找到了与用例预期一致的实现，且关键条件基本完整",
    "部分覆盖": "主流程已经实现，但边界、异常、权限或状态处理不完整",
    "未实现": "在当前变更范围内没有找到对应代码",
    "存在偏差": "代码已有实现，但规则、字段、返回结果或流程与用例不一致",
    "无法判定": "仅凭静态代码和当前材料不足以得出结论，需要人工确认",
}


def rank(status):
    return RISK_ORDER.index(status) if status in RISK_ORDER else 9


def gen(analysis):
    meta = analysis.get("meta", {})
    cases = analysis.get("cases", [])
    dist = analysis.get("distribution", {})
    total = analysis.get("total", len(cases))

    lines = []
    A = lines.append
    A("# 提测前预检报告")
    A("")
    A("> 生成时间：%s　|　由 precheck-before-release 生成（判定需 AI/人工复核后定稿）"
      % analysis.get("generated_at", ""))
    A("")
    A("## 1. 报告说明")
    A("")
    A("本报告为**需求实现与用例预期的一致性静态预检**，不是代码覆盖率报告。它检查的是：")
    A("测试用例中描述的功能、业务规则与异常处理，能否在本次代码变更（Git Diff）中找到对应实现。")
    A("判定结论均附代码依据；其中「无法判定」不代表没有实现，而是静态代码无法确认，需人工核对公共组件、配置中心或运行时行为。")
    A("")
    A("## 2. 检查元信息")
    A("")
    A("| 项目 | 值 |")
    A("| --- | --- |")
    A("| 仓库 | %s |" % meta.get("repo", ""))
    A("| 对比模式 | %s |" % (meta.get("mode_desc") or meta.get("mode", "")))
    A("| 基准分支 | %s |" % (meta.get("base") or "-"))
    A("| 功能分支 | %s |" % (meta.get("feature") or "-"))
    A("| 用例文件 | %s |" % meta.get("cases_file", ""))
    A("| 用例总数 | %d |" % total)
    A("")
    A("## 3. 整体分布")
    A("")
    A("| 判定状态 | 用例数 | 占比 |")
    A("| --- | --- | --- |")
    for s in sorted(dist.keys(), key=rank):
        cnt = dist[s]
        A("| %s | %d | %.0f%% |" % (s, cnt, cnt / total * 100 if total else 0))
    A("")
    A("> 提示：该分布用于快速判断是否具备提测条件，不能直接当作质量结论；「未实现/存在偏差」先与开发确认。")
    A("")
    A("## 4. 高风险缺口")
    A("")
    A("以下条目优先处理：阻塞主流程、影响数据正确性、或存在实现偏差（建议按表格顺序同步开发）。")
    A("")
    A("| 用例 | 标题 | 判定 | 优先级 | 主要问题 |")
    A("| --- | --- | --- | --- | --- |")
    high_risk = [c for c in cases if c.get("status") != "已覆盖"]
    for c in sorted(high_risk, key=lambda x: rank(x.get("status", ""))):
        problem = (c.get("reason") or "").split("。")[0]
        A("| %s | %s | %s | %s | %s |" % (
            c.get("id", "-"), c.get("title", ""), c.get("status", ""),
            c.get("priority", "-"), problem))
    A("")
    A("## 5. 逐条证据")
    A("")
    for c in cases:
        A("### %s　%s — %s" % (c.get("id", "-"), c.get("title", ""), c.get("status", "")))
        A("")
        A("- **关联文件**：%s" % ("、".join(c.get("files_hit", [])) or "（本次变更范围内无命中）"))
        if c.get("evidence"):
            locs = ["%s:%s" % (e["file"], e["line"]) for e in c["evidence"][:5]]
            A("- **代码位置**：%s" % "、".join(locs))
            A("- **已找到实现（摘要）**：")
            for e in c["evidence"][:5]:
                A("  - `%s:%s`　%s" % (e["file"], e["line"], e["text"][:80]))
        else:
            A("- **已找到实现（摘要）**：（本次变更范围内未找到）")
        A("- **规则类型**：用例 %s　/　代码命中 %s" % (
            "、".join(c.get("rule_types_in_case", [])) or "-",
            "、".join(c.get("rule_types_matched", [])) or "-"))
        A("- **结论依据**：%s" % c.get("reason", ""))
        A("- **缺少/不一致**：%s" % (c.get("missing") or "-"))
        A("- **建议处理**：%s" % c.get("suggestion", ""))
        A("")
    A("## 附：判定维度说明")
    A("")
    for s in RISK_ORDER:
        A("- **%s**：%s" % (s, STATUS_LEGEND.get(s, "")))
    A("")
    A("---")
    A("> 报告由 precheck-before-release 生成。判定为草稿结论，最终结论以 AI/人工复核为准。")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="生成 Markdown 预检报告（提测前预检）")
    ap.add_argument("--analysis", required=True, help="analysis.json 路径")
    ap.add_argument("--out", required=True, help="输出报告路径（.md）")
    args = ap.parse_args()

    with open(args.analysis, "r", encoding="utf-8") as f:
        analysis = json.load(f)

    md = gen(analysis)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)
    print("报告已生成: %s" % args.out)


if __name__ == "__main__":
    main()
