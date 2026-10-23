#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析测试用例文件（Excel / CSV / Markdown 表格）为结构化 JSON —— 提测前预检第二步。

支持表头（自动模糊匹配）：
  用例编号 / 用例名称 / 模块 / 优先级 / 前置条件 / 操作步骤 / 预期结果 / 标签

用法：
  python3 parse_cases.py --file cases.xlsx --out cases.json
  python3 parse_cases.py --file cases.csv --out cases.json
  python3 parse_cases.py --file cases.md --out cases.json

输出 JSON 结构（cases.json）：
  {"file": "...", "total": N, "cases": [{"id","title","module","priority",
   "preconditions","steps","expected","tags"}]}
"""

import argparse
import csv
import json
import re
import sys

HEADER_ALIASES = {
    "id": ["用例编号", "编号", "用例id", "case_id", "id", "用例id编号", "用例标识"],
    "title": ["用例名称", "用例标题", "标题", "名称", "用例名", "场景", "场景名称", "测试名称"],
    "module": ["模块", "所属模块", "功能模块", "模块名称", "一级模块", "菜单"],
    "preconditions": ["前置条件", "预置条件", "前提条件", "前置", "初始条件", "前置状态", "准备条件"],
    "steps": ["操作步骤", "步骤", "测试步骤", "操作", "执行步骤", "步骤描述", "用例步骤"],
    "expected": ["预期结果", "期望结果", "预期", "期望", "预期输出", "验证点", "结果"],
    "priority": ["优先级", "级别", "重要级别", "用例优先级", "p"],
    "tags": ["标签", "类型", "用例类型", "类别", "功能点", "业务规则", "验证类型"],
}


def normalize(text):
    return re.sub(r"\s+", "", str(text)).lower()


def map_header(raw_headers):
    """表头 -> 字段名 映射；精确匹配优先，其次包含匹配"""
    mapping = {}
    for idx, raw in enumerate(raw_headers):
        key = normalize(raw)
        if not key:
            continue
        for field, aliases in HEADER_ALIASES.items():
            if any(key == normalize(a) or key in normalize(a) or normalize(a) in key for a in aliases):
                mapping[idx] = field
                break
    return mapping


def clean_cell(value):
    if value is None:
        return ""
    return str(value).strip()


def build_case(row, mapping):
    case = {k: "" for k in HEADER_ALIASES}
    for idx, field in mapping.items():
        if idx < len(row):
            case[field] = clean_cell(row[idx])
    return case


def is_empty(case):
    return not (case["id"] or case["title"] or case["steps"] or case["expected"])


def parse_xlsx(path):
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("错误: 解析 xlsx 需要 openpyxl，请先安装（pip install openpyxl）", file=sys.stderr)
        sys.exit(1)
    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    mapping = map_header(rows[0])
    cases = []
    for row in rows[1:]:
        case = build_case(row, mapping)
        if not is_empty(case):
            cases.append(case)
    return cases


def parse_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    mapping = map_header(rows[0])
    cases = []
    for row in rows[1:]:
        case = build_case(row, mapping)
        if not is_empty(case):
            cases.append(case)
    return cases


def parse_md(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    table_rows = []
    for line in lines:
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            table_rows.append(cells)
    if not table_rows:
        return []
    mapping = map_header(table_rows[0])
    cases = []
    for cells in table_rows[1:]:
        if all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
            continue  # 表头分隔行
        case = build_case(cells, mapping)
        if not is_empty(case):
            cases.append(case)
    return cases


def main():
    ap = argparse.ArgumentParser(description="解析测试用例文件（提测前预检）")
    ap.add_argument("--file", required=True, help="测试用例文件：.xlsx / .csv / .md")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    args = ap.parse_args()

    path = args.file.lower()
    if path.endswith(".xlsx"):
        cases = parse_xlsx(args.file)
    elif path.endswith(".csv"):
        cases = parse_csv(args.file)
    elif path.endswith(".md"):
        cases = parse_md(args.file)
    else:
        print("错误: 仅支持 .xlsx / .csv / .md", file=sys.stderr)
        sys.exit(1)

    if not cases:
        print("警告: 未解析到任何用例，请检查表头是否在支持列表中", file=sys.stderr)

    result = {"file": args.file, "total": len(cases), "cases": cases}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("已解析 %d 条用例，输出: %s" % (len(cases), args.out))


if __name__ == "__main__":
    main()
