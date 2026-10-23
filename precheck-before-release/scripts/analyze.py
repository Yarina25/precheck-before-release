#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将测试用例与代码变更逐条关联，生成判定草稿 —— 提测前预检第三步。

判定维度（五档）：已覆盖 / 部分覆盖 / 未实现 / 存在偏差 / 无法判定

设计说明：
  - 业务规则类型仅从「用例名称 + 操作步骤 + 预期结果」提取（前置条件是环境准备，
    不参与规则判定，避免"已登录系统"等污染规则类型）。
  - 代码检索同时匹配中英文关键词（中文注释里的规则描述同样算证据）。
  - 存在 TODO/占位标记且与用例业务规则（长度/金额/去重/权限/状态等）相关时，
    判为「存在偏差」；与用例规则无关的占位行不触发。

重要：本脚本输出的是"可复核草稿"。规则是否真正一致、边界是否完整等语义判断，
需由 AI 结合 diff_text 复核后定稿；无法判定的条目应人工确认，不要强行下结论。

用法：
  python3 analyze.py --diff diff.json --cases cases.json --out analysis.json
"""

import argparse
import json
import re
from datetime import datetime

# 规则类型：zh = 用例文本/中文注释中的关键词；code = 代码新增行中的关键词
RULE_PATTERNS = {
    "date": {
        "zh": ["日期", "时间", "早于", "晚于", "不能早于", "有效期", "结束日期", "开始日期", "到期", "过期"],
        "code": ["date", "start_date", "end_date", "expire", "deadline", "duration", "valid", "datetime", "timedelta"],
    },
    "required": {
        "zh": ["必填", "非空", "不能为空", "不允许为空", "必选", "缺少", "未填写", "为空"],
        "code": ["required", "not null", "is none", "missing", "empty", "strip", "必填"],
    },
    "length": {
        "zh": ["长度", "位数", "超长", "最大长度", "最多", "最少", "限制在", "字符"],
        "code": ["len(", "length", "max_len", "max_length", "truncate", "chars", "> 50", "< 50", "50"],
    },
    "range": {
        "zh": ["大于", "小于", "介于", "之间", "不超过", "至少", "最高", "最低", "最大", "最小"],
        "code": [">", "<", ">=", "<=", "max(", "min(", "范围"],
    },
    "status": {
        "zh": ["状态", "流转", "变更", "切换", "审核", "审批", "作废", "生效", "失效", "退回", "驳回"],
        "code": ["status", "state", "flow", "approve", "reject", "active", "draft", "pending", "terminated", "cancel"],
    },
    "permission": {
        "zh": ["权限", "无权", "不允许", "只能", "仅", "角色", "数据隔离", "不可见", "越权", "访问控制", "管理员"],
        "code": ["permission", "role", "auth", "has_permission", "acl", "scope", "filter", "is_admin", "admin"],
    },
    "dedup": {
        "zh": ["重复", "唯一", "去重", "重复提交", "幂等", "已存在", "不能重复"],
        "code": ["duplicate", "unique", "exists", "dedup", "idempotent", "already", "唯一"],
    },
    "enum": {
        "zh": ["只能为", "必须是", "只能是", "支持", "枚举", "取值", "可选值"],
        "code": ["in (", "in [", "allowed", "choices", "enum", "== '", '== "'],
    },
    "amount": {
        "zh": ["金额", "价格", "费用", "累计", "合计", "余额"],
        "code": ["amount", "price", "fee", "total", "balance", "money", "rent", "金额"],
    },
    "error": {
        "zh": ["提示", "报错", "错误", "异常", "拒绝", "失败", "返回", "校验不通过", "非法", "统一错误码"],
        "code": ["raise", "error", "exception", "fail", "invalid", "return false", "return {", "code 400", "4001", "message"],
    },
    "auth": {
        "zh": ["登录", "token", "鉴权", "认证", "未登录"],
        "code": ["token", "login", "auth", "session", "unauthorized"],
    },
}

# 存在 TODO/占位标记时会触发「存在偏差」的业务规则类型（通用校验不在此列）
PLACEHOLDER_RULES = {"length", "amount", "dedup", "permission", "status", "enum", "range", "date"}

IDENT_STOPWORDS = {
    "the", "and", "for", "with", "is", "are", "of", "to", "in", "at", "be",
    "or", "if", "on", "by", "from", "not", "no", "check", "test", "should",
    "must", "verify", "case", "step", "expected", "result", "when", "then",
    "this", "that", "page", "button", "input", "click", "open", "enter",
}

PLACEHOLDER_RE = re.compile(r"TODO|FIXME|XXX|待实现|未实现|占位|待补充", re.IGNORECASE)
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{1,}")


def extract_identifiers(text):
    """从用例文本提取英文标识符（含 camelCase 拆分），用于匹配代码中的变量/字段名"""
    tokens = set()
    for t in IDENT_RE.findall(text):
        low = t.lower()
        if low in IDENT_STOPWORDS or len(low) < 2:
            continue
        tokens.add(t)
        parts = re.findall(r"[A-Za-z][a-z]*", t)
        for p in parts:
            if len(p) >= 2 and p.lower() not in IDENT_STOPWORDS:
                tokens.add(p)
    return tokens


def rule_types_in_case(case_text):
    found = set()
    for rule, pats in RULE_PATTERNS.items():
        if any(k in case_text for k in pats["zh"]):
            found.add(rule)
    return found


def rules_in_line(low):
    """一条代码行命中哪些规则类型（中英文关键词都算）"""
    found = set()
    for rule, pats in RULE_PATTERNS.items():
        if any(p in low for p in pats["zh"]) or any(p.lower() in low for p in pats["code"]):
            found.add(rule)
    return found


def search_diff(diff_data, case):
    """在本次变更的新增代码中检索与用例相关的证据，输出命中信息"""
    rule_text = " ".join([case.get("title", ""), case.get("steps", ""), case.get("expected", "")])
    ids = extract_identifiers(rule_text)
    case_rules = rule_types_in_case(rule_text)

    # 检索词 = 用例英文标识符 + 用例所涉规则的中英文关键词
    keywords = set(ids)
    for rule in case_rules:
        keywords.update(RULE_PATTERNS[rule]["zh"])
        keywords.update(RULE_PATTERNS[rule]["code"])

    hits = []          # [{"file","line","text"}]
    hit_rules = set()  # 命中行所体现的规则类型
    files_hit = set()

    def scan_line(file_path, line_no, text):
        low = text.lower()
        if not low.strip():
            return
        if not any(k.lower() in low for k in keywords if k):
            return
        entry = {"file": file_path, "line": line_no, "text": text.strip()}
        hits.append(entry)
        files_hit.add(file_path)
        hit_rules.update(rules_in_line(low))

    for f in diff_data.get("files", []):
        if f.get("binary"):
            continue
        for h in f.get("hunks", []):
            for e in h.get("added", []):
                scan_line(f["path"], e["line"], e["text"])

    for u in diff_data.get("untracked", []):
        for idx, line in enumerate(u.get("text", "").splitlines(), start=1):
            scan_line(u["path"], idx, line)

    # 去重并限制证据条数
    seen = set()
    dedup_hits = []
    for ht in hits:
        key = (ht["file"], ht["line"])
        if key in seen:
            continue
        seen.add(key)
        dedup_hits.append(ht)

    # 与用例业务规则相关的占位行（TODO 标记）
    placeholder_rules = set()
    for ht in dedup_hits:
        if PLACEHOLDER_RE.search(ht["text"]):
            placeholder_rules.update(rules_in_line(ht["text"].lower()) & PLACEHOLDER_RULES)

    return {
        "hits": dedup_hits[:20],
        "files_hit": sorted(files_hit),
        "hit_rules": hit_rules,
        "case_rules": case_rules,
        "placeholder_rules": placeholder_rules,
        "identifiers": sorted(ids),
        "generic": not ids and not case_rules,
    }


def draft_status(info):
    """依据命中情况给出草稿判定（五档）+ 结论依据 + 缺失说明"""
    hits = info["hits"]
    case_rules = info["case_rules"]
    hit_rules = info["hit_rules"]
    placeholder_rules = info["placeholder_rules"] & case_rules

    if not hits:
        if info["generic"]:
            return ("无法判定",
                    "用例缺少明确的规则关键词与标识符，无法从静态代码确认变更范围内是否已有实现",
                    "用例规则描述过泛，建议补充具体字段/规则后重跑或人工确认")
        return ("未实现",
                "在本次代码变更中未找到与该用例相关的实现（若逻辑位于未变更的公共代码/配置中心，请人工确认后改判）",
                "变更范围内无对应代码")

    if placeholder_rules:
        return ("存在偏差",
                "变更代码中与用例业务规则（%s）相关的位置存在 TODO/占位/待实现标记，与用例预期不一致，建议确认是否已真正实现"
                % "、".join(sorted(placeholder_rules)),
                "存在 TODO/占位标记，未确认是否为最终实现")

    if not case_rules:
        if len(hits) >= 2:
            return ("已覆盖",
                    "变更代码中存在相关实现，但用例缺少明确的规则描述，建议冒烟时重点验证关键分支",
                    "用例未描述明确规则，仅作参考")
        return ("无法判定",
                "有相关代码，但用例未描述明确规则，无法确认实现是否满足预期",
                "需补充用例规则描述后确认")

    matched = case_rules & hit_rules
    unmatched = sorted(case_rules - hit_rules)
    ratio = len(matched) / len(case_rules)

    if ratio >= 1.0:
        return ("已覆盖",
                "变更代码中存在与用例规则匹配的实现，建议冒烟时重点验证关键分支",
                "规则类型均已命中，仍需确认阈值/分支是否完全一致")
    if ratio > 0:
        return ("部分覆盖",
                "主流程已实现，但以下规则未在变更中找到对应实现：%s" % ("、".join(unmatched) or "边界/异常/状态处理"),
                "未匹配规则：" + "、".join(unmatched) if unmatched else "边界/异常/状态处理不完整")
    return ("无法判定",
            "仅找到部分相关代码，静态代码不足以确认规则是否完整实现（可能依赖公共组件或运行时行为）",
            "命中证据不足以覆盖用例规则")


SUGGESTIONS = {
    "已覆盖": "冒烟阶段重点验证该用例的关键分支与边界；若依赖未变更的公共模块，请顺带人工确认该模块实现。",
    "部分覆盖": "优先补齐缺失规则（见缺少/不一致）；若实现确实位于未变更代码中，请补充说明并改判。",
    "未实现": "同步开发补充对应实现；若确认逻辑已存在于未变更的公共代码/配置中心，请改判为已覆盖或无法判定并注明位置。",
    "存在偏差": "与开发对齐占位/待实现位置，确认是未完成还是可接受范围，并同步测试冒烟重点。",
    "无法判定": "人工确认（公共组件、配置中心、运行时行为等），确认后改判并记录结论，不要强行下结论。",
}


def analyze(diff_data, cases_data):
    results = []
    for case in cases_data.get("cases", []):
        info = search_diff(diff_data, case)
        status, reason, missing = draft_status(info)
        results.append({
            "id": case.get("id") or "-",
            "title": case.get("title") or "",
            "module": case.get("module") or "",
            "priority": case.get("priority") or "",
            "status": status,
            "confidence": "high" if status in ("存在偏差", "未实现") and not info["generic"] else "medium",
            "reason": reason,
            "missing": missing,
            "suggestion": SUGGESTIONS.get(status, ""),
            "files_hit": info["files_hit"],
            "rule_types_in_case": sorted(info["case_rules"]),
            "rule_types_matched": sorted(info["hit_rules"]),
            "identifiers": info["identifiers"],
            "evidence": info["hits"],
        })
    return results


def main():
    ap = argparse.ArgumentParser(description="用例与代码变更逐条关联（提测前预检）")
    ap.add_argument("--diff", required=True, help="collect_diff.py 输出的 diff.json")
    ap.add_argument("--cases", required=True, help="parse_cases.py 输出的 cases.json")
    ap.add_argument("--out", required=True, help="输出 analysis.json")
    args = ap.parse_args()

    with open(args.diff, "r", encoding="utf-8") as f:
        diff_data = json.load(f)
    with open(args.cases, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    results = analyze(diff_data, cases_data)

    distribution = {}
    for r in results:
        distribution[r["status"]] = distribution.get(r["status"], 0) + 1

    analysis = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "meta": {
            "repo": diff_data.get("repo", ""),
            "mode": diff_data.get("mode", ""),
            "mode_desc": diff_data.get("mode_desc", ""),
            "base": diff_data.get("base", ""),
            "feature": diff_data.get("feature", ""),
            "cases_file": cases_data.get("file", ""),
        },
        "total": len(results),
        "distribution": distribution,
        "cases": results,
        "note": "本文件为可复核草稿：请由 AI 结合 diff_text 复核（尤其 无法判定/未实现/存在偏差），修改 status/reason/missing 后重新运行 report.py 定稿。",
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    print("已分析 %d 条用例：" % len(results))
    for status, cnt in sorted(distribution.items(), key=lambda x: -x[1]):
        print("  %s: %d" % (status, cnt))
    print("输出: %s" % args.out)


if __name__ == "__main__":
    main()
