#!/usr/bin/env bash
# 演示工程构建脚本：模拟线上分支 prod_1.0.0 与开发分支 feat_tenant_lease
# 产物：repo/（git 仓库）、cases/lease_cases.xlsx（测试用例）
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$BASE/repo"

rm -rf "$REPO"
mkdir -p "$REPO" "$BASE/cases"

cd "$REPO"
git init -q -b prod_1.0.0

# ---- 基准版本（prod_1.0.0）----
cat > auth.py <<'EOF'
"""统一鉴权公共模块（本次变更未涉及）"""


def has_permission(user, perm):
    if user is None:
        return False
    return perm in user.get("permissions", [])
EOF

cat > lease_service.py <<'EOF'
"""租赁合同服务（prod_1.0.0）"""
import uuid


class LeaseService:
    """租赁合同服务"""

    def create_lease(self, data):
        contract = {
            "id": str(uuid.uuid4()),
            "tenant_id": data["tenant_id"],
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "rent": data["rent"],
            "status": "DRAFT",
        }
        save(contract)
        return contract

    def update_lease(self, contract_id, data):
        contract = find(contract_id)
        contract.update(data)
        save(contract)
        return contract
EOF

git add -A
git -c user.name=demo -c user.email=demo@example.com commit -qm "prod 1.0.0 基线：租赁合同基础增删改查"

# ---- 开发分支（feat_tenant_lease）----
git checkout -q -b feat_tenant_lease

cat > lease_service.py <<'EOF'
"""租赁合同服务（feat_tenant_lease）"""
import uuid


def _validate(data):
    # 必填字段校验
    for field in ("tenant_id", "start_date", "end_date", "rent"):
        if not data.get(field):
            raise ValueError(f"{field} 为必填项")

    # 租户名称必填（长度上限校验暂未实现）
    if not data.get("tenant_name", "").strip():
        raise ValueError("租户名称为必填项")

    # 合同结束日期不能早于开始日期
    if data["end_date"] < data["start_date"]:
        raise ValueError("合同结束日期不能早于开始日期")

    # 租金必须大于0
    if data["rent"] <= 0:
        raise ValueError("租金必须大于0")

    # 金额上限校验（占位，待实现）
    # TODO: 合同金额超过单笔上限时应拒绝


class LeaseService:
    """租赁合同服务"""

    def create_lease(self, data, user=None):
        try:
            # 权限：非管理员不能审批（校验逻辑依赖公共 auth 模块）
            if not auth.has_permission(user, "LEASE_APPROVE"):
                raise PermissionError("非管理员不能审批")
            _validate(data)
            contract = {
                "id": str(uuid.uuid4()),
                "tenant_id": data["tenant_id"],
                "tenant_name": data.get("tenant_name"),
                "start_date": data["start_date"],
                "end_date": data["end_date"],
                "rent": data["rent"],
                "status": "DRAFT",
            }
            save(contract)
            return {"code": 0, "data": contract}
        except ValueError as e:
            return {"code": 4001, "message": str(e)}
        except PermissionError as e:
            return {"code": 4003, "message": str(e)}

    def update_lease(self, contract_id, data):
        contract = find(contract_id)
        # 已生效合同不可修改（仅拦截 ACTIVE，TERMINATED/审批中状态未处理）
        if contract["status"] == "ACTIVE":
            raise PermissionError("已生效合同不可修改")
        contract.update(data)
        save(contract)
        return contract
EOF

git add -A
git -c user.name=demo -c user.email=demo@example.com commit -qm "feat: 租赁合同必填/日期/租金校验与状态流转限制"

# ---- 生成测试用例 xlsx ----
python3 - "$BASE/cases/lease_cases.xlsx" <<'PYEOF'
import openpyxl
import sys

out = sys.argv[1]
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "租赁合同用例"
ws.append(["用例编号", "用例名称", "模块", "优先级", "前置条件", "操作步骤", "预期结果"])

rows = [
    ["TC-001", "正常创建租赁合同", "合同管理", "P0",
     "已登录系统，拥有合同创建权限",
     "1. 进入「租赁合同」页面\n2. 填写租户、房源、租赁起止日期、租金等必填字段\n3. 点击「保存」",
     "创建成功，返回合同编号，状态为草稿"],
    ["TC-002", "合同结束日期早于开始日期被拒绝", "合同管理", "P0",
     "已登录系统",
     "1. 进入创建合同页面\n2. 结束日期填写早于开始日期的值\n3. 点击「保存」",
     "校验不通过，提示「合同结束日期不能早于开始日期」，不创建合同"],
    ["TC-003", "租金必须大于0", "合同管理", "P0",
     "已登录系统",
     "1. 进入创建合同页面\n2. 租金填写0或负数\n3. 点击「保存」",
     "校验不通过，提示「租金必须大于0」"],
    ["TC-004", "租户名称必填且长度不超过50字符", "合同管理", "P1",
     "已登录系统",
     "1. 创建合同时租户名称留空\n2. 点击保存",
     "必填校验生效；名称长度超过50字符时应拒绝保存"],
    ["TC-005", "同一房源同一租户重复提交提示合同已存在", "合同管理", "P1",
     "已存在一份未结束的合同",
     "1. 对同一房源同一租户再次创建合同\n2. 点击保存",
     "提示「合同已存在」，不重复创建"],
    ["TC-006", "已生效合同不可修改", "合同管理", "P1",
     "存在一份已生效合同",
     "1. 打开已生效合同详情\n2. 尝试修改租期或租金\n3. 点击保存",
     "提示「已生效合同不可修改」；草稿状态合同可正常修改"],
    ["TC-007", "无审批权限用户提交审批被拒绝", "合同管理", "P1",
     "当前用户无审批权限",
     "1. 打开草稿合同\n2. 点击「提交审批」",
     "提示无权限，审批不生效（权限校验）"],
    ["TC-008", "合同金额超过单笔上限应拒绝", "合同管理", "P1",
     "已登录系统",
     "1. 填写租金使合同总金额超过单笔上限\n2. 点击保存",
     "拒绝保存并提示金额超限"],
    ["TC-009", "最大续约次数由配置中心控制", "合同管理", "P2",
     "已登录系统",
     "1. 对同一合同连续续约超过最大次数\n2. 点击续约",
     "超过配置上限时拒绝续约"],
    ["TC-010", "创建失败时返回统一错误码", "接口层", "P1",
     "已登录系统",
     "1. 调用创建合同接口并传入非法参数\n2. 查看响应",
     "返回统一错误码结构（code/message），业务异常不返回200"],
]
for r in rows:
    ws.append(r)
wb.save(out)
print("用例文件已生成:", out)
PYEOF

echo "✅ 演示工程构建完成：$BASE"
echo "   git 仓库: $REPO （分支 prod_1.0.0 / feat_tenant_lease）"
echo "   用例文件: $BASE/cases/lease_cases.xlsx"
