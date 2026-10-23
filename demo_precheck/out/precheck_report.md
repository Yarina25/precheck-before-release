# 提测前预检报告

> 生成时间：2026-10-22T13:17:26　|　由 precheck-before-release 生成（判定需 AI/人工复核后定稿）

## 1. 报告说明

本报告为**需求实现与用例预期的一致性静态预检**，不是代码覆盖率报告。它检查的是：
测试用例中描述的功能、业务规则与异常处理，能否在本次代码变更（Git Diff）中找到对应实现。
判定结论均附代码依据；其中「无法判定」不代表没有实现，而是静态代码无法确认，需人工核对公共组件、配置中心或运行时行为。

## 2. 检查元信息

| 项目 | 值 |
| --- | --- |
| 仓库 | /home/user/Doubao/chats/38448592381610754/demo_precheck/repo |
| 对比模式 | PR 范围 prod_1.0.0...feat_tenant_lease（三点语法，从共同祖先开始比较） |
| 基准分支 | prod_1.0.0 |
| 功能分支 | feat_tenant_lease |
| 用例文件 | ./cases/lease_cases.xlsx |
| 用例总数 | 10 |

## 3. 整体分布

| 判定状态 | 用例数 | 占比 |
| --- | --- | --- |
| 存在偏差 | 1 | 10% |
| 未实现 | 1 | 10% |
| 部分覆盖 | 2 | 20% |
| 无法判定 | 2 | 20% |
| 已覆盖 | 4 | 40% |

> 提示：该分布用于快速判断是否具备提测条件，不能直接当作质量结论；「未实现/存在偏差」先与开发确认。

## 4. 高风险缺口

以下条目优先处理：阻塞主流程、影响数据正确性、或存在实现偏差（建议按表格顺序同步开发）。

| 用例 | 标题 | 判定 | 优先级 | 主要问题 |
| --- | --- | --- | --- | --- |
| TC-008 | 合同金额超过单笔上限应拒绝 | 存在偏差 | P1 | 变更代码中与用例业务规则（amount）相关的位置存在 TODO/占位/待实现标记，与用例预期不一致，建议确认是否已真正实现 |
| TC-005 | 同一房源同一租户重复提交提示合同已存在 | 未实现 | P1 | 命中行均为必填/日期/租金校验的 raise 与统一错误码返回，与"重复提交"无关；本次变更代码中无任何去重/幂等/已存在判断逻辑 |
| TC-004 | 租户名称必填且长度不超过50字符 | 部分覆盖 | P1 | 租户名称必填已实现（lease_service.py:13），但长度不超过50字符的校验缺失（注释第11行明确标注"暂未实现"） |
| TC-006 | 已生效合同不可修改 | 部分覆盖 | P1 | 已实现"已生效合同不可修改"（lease_service.py:56），但仅拦截 ACTIVE 状态，TERMINATED、审批中等其他不可编辑状态未处理，边界不完整 |
| TC-007 | 无审批权限用户提交审批被拒绝 | 无法判定 | P1 | 权限校验调用公共模块 auth.has_permission（lease_service.py:34），该模块未包含在本次变更中，角色判定是否完整、是否覆盖全部审批入口需人工确认 |
| TC-009 | 最大续约次数由配置中心控制 | 无法判定 | P2 | 最大续约次数由配置中心控制，属运行时行为；本次变更代码中无相关实现，静态代码无法确认是否已生效 |

## 5. 逐条证据

### TC-001　正常创建租赁合同 — 已覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:5、lease_service.py:6、lease_service.py:7、lease_service.py:9、lease_service.py:11
- **已找到实现（摘要）**：
  - `lease_service.py:5`　def _validate(data):
  - `lease_service.py:6`　# 必填字段校验
  - `lease_service.py:7`　for field in ("tenant_id", "start_date", "end_date", "rent"):
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:11`　# 租户名称必填（长度上限校验暂未实现）
- **规则类型**：用例 date、error、required、status　/　代码命中 amount、auth、date、enum、error、length、permission、range、required、status
- **结论依据**：变更代码中存在与用例规则匹配的实现，建议冒烟时重点验证关键分支
- **缺少/不一致**：规则类型均已命中，仍需确认阈值/分支是否完全一致
- **建议处理**：冒烟阶段重点验证该用例的关键分支与边界；若依赖未变更的公共模块，请顺带人工确认该模块实现。

### TC-002　合同结束日期早于开始日期被拒绝 — 已覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:5、lease_service.py:7、lease_service.py:9、lease_service.py:13、lease_service.py:15
- **已找到实现（摘要）**：
  - `lease_service.py:5`　def _validate(data):
  - `lease_service.py:7`　for field in ("tenant_id", "start_date", "end_date", "rent"):
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:15`　# 合同结束日期不能早于开始日期
- **规则类型**：用例 date、error　/　代码命中 amount、date、enum、error、permission、range、required、status
- **结论依据**：变更代码中存在与用例规则匹配的实现，建议冒烟时重点验证关键分支
- **缺少/不一致**：规则类型均已命中，仍需确认阈值/分支是否完全一致
- **建议处理**：冒烟阶段重点验证该用例的关键分支与边界；若依赖未变更的公共模块，请顺带人工确认该模块实现。

### TC-003　租金必须大于0 — 已覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:16、lease_service.py:17、lease_service.py:19
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:16`　if data["end_date"] < data["start_date"]:
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:19`　# 租金必须大于0
- **规则类型**：用例 error、range　/　代码命中 amount、date、error、permission、range、required、status
- **结论依据**：变更代码中存在与用例规则匹配的实现，建议冒烟时重点验证关键分支
- **缺少/不一致**：规则类型均已命中，仍需确认阈值/分支是否完全一致
- **建议处理**：冒烟阶段重点验证该用例的关键分支与边界；若依赖未变更的公共模块，请顺带人工确认该模块实现。

### TC-004　租户名称必填且长度不超过50字符 — 部分覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:6、lease_service.py:9、lease_service.py:11、lease_service.py:12、lease_service.py:13
- **已找到实现（摘要）**：
  - `lease_service.py:6`　# 必填字段校验
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:11`　# 租户名称必填（长度上限校验暂未实现）
  - `lease_service.py:12`　if not data.get("tenant_name", "").strip():
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
- **规则类型**：用例 error、length、range、required、status　/　代码命中 amount、auth、date、enum、error、length、permission、range、required、status
- **结论依据**：租户名称必填已实现（lease_service.py:13），但长度不超过50字符的校验缺失（注释第11行明确标注"暂未实现"）
- **缺少/不一致**：租户名称长度上限（50字符）校验未实现
- **建议处理**：同步开发补充名称长度校验；补齐后重新执行预检确认。

### TC-005　同一房源同一租户重复提交提示合同已存在 — 未实现

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:17、lease_service.py:21、lease_service.py:24
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:21`　raise ValueError("租金必须大于0")
  - `lease_service.py:24`　# TODO: 合同金额超过单笔上限时应拒绝
- **规则类型**：用例 dedup、error　/　代码命中 amount、date、error、permission、range、required、status
- **结论依据**：命中行均为必填/日期/租金校验的 raise 与统一错误码返回，与"重复提交"无关；本次变更代码中无任何去重/幂等/已存在判断逻辑
- **缺少/不一致**：重复提交校验（同一房源+同一租户）无对应实现
- **建议处理**：同步开发在创建前查询未结束合同并返回"合同已存在"；实现后回归该用例。

### TC-006　已生效合同不可修改 — 部分覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:17、lease_service.py:21、lease_service.py:24
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:21`　raise ValueError("租金必须大于0")
  - `lease_service.py:24`　# TODO: 合同金额超过单笔上限时应拒绝
- **规则类型**：用例 error、status　/　代码命中 amount、auth、date、enum、error、permission、range、required、status
- **结论依据**：已实现"已生效合同不可修改"（lease_service.py:56），但仅拦截 ACTIVE 状态，TERMINATED、审批中等其他不可编辑状态未处理，边界不完整
- **缺少/不一致**：状态边界不完整：仅拦截 ACTIVE，TERMINATED/审批中未处理
- **建议处理**：补齐不可编辑状态集合（ACTIVE/TERMINATED/审批中等），或确认业务上仅 ACTIVE 需拦截。

### TC-007　无审批权限用户提交审批被拒绝 — 无法判定

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:17、lease_service.py:21、lease_service.py:24
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:21`　raise ValueError("租金必须大于0")
  - `lease_service.py:24`　# TODO: 合同金额超过单笔上限时应拒绝
- **规则类型**：用例 error、permission、status　/　代码命中 amount、auth、date、enum、error、permission、range、required、status
- **结论依据**：权限校验调用公共模块 auth.has_permission（lease_service.py:34），该模块未包含在本次变更中，角色判定是否完整、是否覆盖全部审批入口需人工确认
- **缺少/不一致**：依赖未变更的公共 auth 模块，静态代码无法确认完整性与覆盖面
- **建议处理**：人工确认 auth 模块的 LEASE_APPROVE 权限判定实现与调用点覆盖；确认后改判。

### TC-008　合同金额超过单笔上限应拒绝 — 存在偏差

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:7、lease_service.py:9、lease_service.py:13、lease_service.py:17、lease_service.py:20
- **已找到实现（摘要）**：
  - `lease_service.py:7`　for field in ("tenant_id", "start_date", "end_date", "rent"):
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:20`　if data["rent"] <= 0:
- **规则类型**：用例 amount、error　/　代码命中 amount、date、enum、error、permission、range、required、status
- **结论依据**：变更代码中与用例业务规则（amount）相关的位置存在 TODO/占位/待实现标记，与用例预期不一致，建议确认是否已真正实现
- **缺少/不一致**：存在 TODO/占位标记，未确认是否为最终实现
- **建议处理**：与开发对齐占位/待实现位置，确认是未完成还是可接受范围，并同步测试冒烟重点。

### TC-009　最大续约次数由配置中心控制 — 无法判定

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:16、lease_service.py:17、lease_service.py:19
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:16`　if data["end_date"] < data["start_date"]:
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:19`　# 租金必须大于0
- **规则类型**：用例 error、range　/　代码命中 amount、date、error、permission、range、required、status
- **结论依据**：最大续约次数由配置中心控制，属运行时行为；本次变更代码中无相关实现，静态代码无法确认是否已生效
- **缺少/不一致**：配置中心/运行时行为，超出静态预检能力
- **建议处理**：人工确认配置项是否存在、是否接入续约接口；确认后改判为已覆盖或未实现。

### TC-010　创建失败时返回统一错误码 — 已覆盖

- **关联文件**：lease_service.py
- **代码位置**：lease_service.py:9、lease_service.py:13、lease_service.py:17、lease_service.py:21、lease_service.py:24
- **已找到实现（摘要）**：
  - `lease_service.py:9`　raise ValueError(f"{field} 为必填项")
  - `lease_service.py:13`　raise ValueError("租户名称为必填项")
  - `lease_service.py:17`　raise ValueError("合同结束日期不能早于开始日期")
  - `lease_service.py:21`　raise ValueError("租金必须大于0")
  - `lease_service.py:24`　# TODO: 合同金额超过单笔上限时应拒绝
- **规则类型**：用例 error　/　代码命中 amount、date、error、permission、range、required、status
- **结论依据**：变更代码中存在与用例规则匹配的实现，建议冒烟时重点验证关键分支
- **缺少/不一致**：规则类型均已命中，仍需确认阈值/分支是否完全一致
- **建议处理**：冒烟阶段重点验证该用例的关键分支与边界；若依赖未变更的公共模块，请顺带人工确认该模块实现。

## 附：判定维度说明

- **存在偏差**：代码已有实现，但规则、字段、返回结果或流程与用例不一致
- **未实现**：在当前变更范围内没有找到对应代码
- **部分覆盖**：主流程已经实现，但边界、异常、权限或状态处理不完整
- **无法判定**：仅凭静态代码和当前材料不足以得出结论，需要人工确认
- **已覆盖**：在变更中找到了与用例预期一致的实现，且关键条件基本完整

---
> 报告由 precheck-before-release 生成。判定为草稿结论，最终结论以 AI/人工复核为准。