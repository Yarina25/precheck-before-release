#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收集 Git 变更并输出结构化 JSON —— 提测前预检第一步。

三种对比模式：
  worktree  日常开发：工作区全部改动（已暂存 + 未暂存 + 未跟踪文件）
  pr        合入评审：base...feature 三点语法，近似一次 PR 的真实变更范围
  staged    提交前自检：仅 git add 的内容

用法：
  python3 collect_diff.py --repo <仓库路径> --mode worktree --out diff.json
  python3 collect_diff.py --repo <仓库路径> --mode pr --base prod_1.0.0 --feature feat_tenant_lease --out diff.json
  python3 collect_diff.py --repo <仓库路径> --mode staged --out diff.json

输出 JSON 结构（diff.json）：
  {
    "repo": "...", "mode": "pr", "mode_desc": "PR 范围 prod_1.0.0...feat_tenant_lease",
    "base": "prod_1.0.0", "feature": "feat_tenant_lease",
    "generated_at": "...",
    "diff_text": "diff 原文（供 AI 语义复核）",
    "files": [
      {"path": "src/lease_service.py", "change_type": "M", "binary": false,
       "additions": 12, "deletions": 3,
       "hunks": [{"start_old": 1, "start_new": 1,
                  "added":   [{"line": 5, "text": "..."}],
                  "removed": [{"line": 4, "text": "..."}]}]}
    ],
    "untracked": [{"path": "...", "text": "未跟踪文件全文"}]   # 仅 worktree 模式
  }
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
DIFF_RE = re.compile(r"^diff --git a/(.*) b/(.*)$")
PLACEHOLDER_RE = re.compile(r"TODO|FIXME|XXX|待实现|未实现|占位|待补充", re.IGNORECASE)


def run_git(repo, args):
    proc = subprocess.run(["git", "-C", repo] + args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("git %s 失败: %s" % (" ".join(args), proc.stderr.strip()))
    return proc.stdout


def parse_name_status(text):
    """解析 git diff --name-status 输出 -> {new_path: 变更类型}"""
    result = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code = parts[0]
        status = code[0]
        if status == "R":
            new_path = parts[2] if len(parts) > 2 else parts[1]
        else:
            new_path = parts[1]
        result[new_path] = status
    return result


def parse_diff(raw):
    """解析 unified diff 原文 -> 按文件分组的变更块列表"""
    blocks = []
    current = None
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                blocks.append(current)
            current = {"path": None, "binary": False, "hunks": [], "raw_lines": []}
        if current is None:
            continue
        current["raw_lines"].append(line)
        m = DIFF_RE.match(line)
        if m and current["path"] is None:
            current["path"] = m.group(2)
        if "Binary files" in line:
            current["binary"] = True
            continue
        hm = HUNK_RE.match(line)
        if hm:
            current["hunks"].append({
                "start_old": int(hm.group(1)),
                "start_new": int(hm.group(3)),
                "added": [],      # [{"line": 新文件行号, "text": ...}]
                "removed": [],    # [{"line": 旧文件行号, "text": ...}]
            })
            continue
        if current["hunks"]:
            h = current["hunks"][-1]
            if h.get("_old_cur") is None:
                h["_old_cur"] = h["start_old"]
                h["_new_cur"] = h["start_new"]
            if line.startswith("+") and not line.startswith("+++"):
                h["added"].append({"line": h["_new_cur"], "text": line[1:]})
                h["_new_cur"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                h["removed"].append({"line": h["_old_cur"], "text": line[1:]})
                h["_old_cur"] += 1
            elif line.startswith(" "):
                h["_new_cur"] += 1
                h["_old_cur"] += 1
    if current is not None:
        blocks.append(current)
    for b in blocks:
        for h in b["hunks"]:
            h.pop("_old_cur", None)
            h.pop("_new_cur", None)
    return blocks


def read_untracked(repo, rel_path):
    """读取未跟踪文本文件全文；非文本返回 None"""
    full = os.path.join(repo, rel_path)
    if not os.path.isfile(full):
        return None
    try:
        with open(full, "r", encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def collect(repo, mode, base, feature):
    if mode == "staged":
        diff_args = ["diff", "--cached", "--unified=4"]
        names_args = ["diff", "--cached", "--name-status"]
        desc = "仅暂存区（已 git add 的内容）"
    elif mode == "pr":
        if not base or not feature:
            raise RuntimeError("pr 模式需要同时提供 --base 和 --feature")
        diff_args = ["diff", "--unified=4", "%s...%s" % (base, feature)]
        names_args = ["diff", "--name-status", "%s...%s" % (base, feature)]
        desc = "PR 范围 %s...%s（三点语法，从共同祖先开始比较）" % (base, feature)
    else:  # worktree
        diff_args = ["diff", "HEAD", "--unified=4"]
        names_args = ["diff", "HEAD", "--name-status"]
        desc = "工作区全部改动（已暂存 + 未暂存）"

    raw_diff = run_git(repo, diff_args)
    name_status = parse_name_status(run_git(repo, names_args))
    blocks = parse_diff(raw_diff)

    files = []
    for b in blocks:
        path = b["path"]
        if path is None:
            continue
        added_cnt = sum(len(h["added"]) for h in b["hunks"])
        removed_cnt = sum(len(h["removed"]) for h in b["hunks"])
        files.append({
            "path": path,
            "change_type": name_status.get(path, "M"),
            "binary": b["binary"],
            "additions": added_cnt,
            "deletions": removed_cnt,
            "hunks": [{
                "start_old": h["start_old"],
                "start_new": h["start_new"],
                "added": h["added"],
                "removed": h["removed"],
            } for h in b["hunks"]],
        })

    untracked = []
    if mode == "worktree":
        st = run_git(repo, ["status", "--porcelain"])
        for line in st.splitlines():
            if line.startswith("??"):
                path = line[3:].strip()
                text = read_untracked(repo, path)
                if text is not None:
                    untracked.append({"path": path, "text": text})

    return {
        "repo": os.path.abspath(repo),
        "mode": mode,
        "mode_desc": desc,
        "base": base or "",
        "feature": feature or "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "diff_text": raw_diff,
        "files": files,
        "untracked": untracked,
    }


def main():
    ap = argparse.ArgumentParser(description="收集 Git 变更（提测前预检）")
    ap.add_argument("--repo", default=".", help="Git 仓库路径（默认当前目录）")
    ap.add_argument("--mode", required=True, choices=["worktree", "pr", "staged"], help="对比模式")
    ap.add_argument("--base", default="", help="基准分支（pr 模式必填）")
    ap.add_argument("--feature", default="", help="功能分支（pr 模式必填）")
    ap.add_argument("--out", required=True, help="输出 JSON 路径")
    args = ap.parse_args()

    try:
        data = collect(args.repo, args.mode, args.base, args.feature)
    except RuntimeError as e:
        print("错误:", e, file=sys.stderr)
        sys.exit(1)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    changed = len(data["files"]) + len(data["untracked"])
    print("已收集 %d 个变更文件（%s），输出: %s" % (changed, data["mode_desc"], args.out))


if __name__ == "__main__":
    main()
