#!/usr/bin/env bash
# 提测前预检一键脚本：收集 diff → 解析用例 → 草稿分析 → 生成报告
#
# 用法示例：
#   bash run_precheck.sh --repo . --mode pr --base prod_1.0.0 --feature feat_tenant_lease --cases cases.xlsx
#   bash run_precheck.sh --repo . --mode worktree --cases cases.xlsx --outdir ./precheck_out
#
# 说明：脚本产出的是草稿分析（analysis.json），建议随后由 AI 结合 diff.json 复核
#       无法判定/未实现/存在偏差 条目后，再运行 report.py 定稿。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="."
MODE=""
BASE=""
FEATURE=""
CASES=""
OUTDIR="./precheck_out"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --mode) MODE="$2"; shift 2 ;;
    --base) BASE="$2"; shift 2 ;;
    --feature) FEATURE="$2"; shift 2 ;;
    --cases) CASES="$2"; shift 2 ;;
    --outdir) OUTDIR="$2"; shift 2 ;;
    -h|--help) sed -n '1,20p' "$0"; exit 0 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

[[ -n "$MODE" ]] || { echo "错误: 缺少 --mode（worktree|pr|staged）"; exit 1; }
[[ -n "$CASES" ]] || { echo "错误: 缺少 --cases 测试用例文件"; exit 1; }

mkdir -p "$OUTDIR"
DIFF_JSON="$OUTDIR/diff.json"
CASES_JSON="$OUTDIR/cases.json"
ANALYSIS_JSON="$OUTDIR/analysis.json"
REPORT_MD="$OUTDIR/precheck_report.md"

echo "[1/4] 收集 Git 变更（mode=$MODE）..."
ARGS=(--repo "$REPO" --mode "$MODE" --out "$DIFF_JSON")
[[ -n "$BASE" ]] && ARGS+=(--base "$BASE")
[[ -n "$FEATURE" ]] && ARGS+=(--feature "$FEATURE")
python3 "$SCRIPT_DIR/collect_diff.py" "${ARGS[@]}"

echo "[2/4] 解析测试用例..."
python3 "$SCRIPT_DIR/parse_cases.py" --file "$CASES" --out "$CASES_JSON"

echo "[3/4] 生成逐条分析草稿..."
python3 "$SCRIPT_DIR/analyze.py" --diff "$DIFF_JSON" --cases "$CASES_JSON" --out "$ANALYSIS_JSON"

echo "[4/4] 生成 Markdown 报告..."
python3 "$SCRIPT_DIR/report.py" --analysis "$ANALYSIS_JSON" --out "$REPORT_MD"

echo ""
echo "✅ 预检完成："
echo "   diff:      $DIFF_JSON"
echo "   cases:     $CASES_JSON"
echo "   analysis:  $ANALYSIS_JSON"
echo "   报告:      $REPORT_MD"
echo ""
echo "下一步：请 AI 复核 analysis.json 中的草稿判定（尤其 无法判定/未实现/存在偏差），"
echo "        修改后重新运行 report.py 定稿。"
