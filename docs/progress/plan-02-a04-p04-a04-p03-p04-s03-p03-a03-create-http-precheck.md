# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A03：PlanVersion 创建 HTTP 前置核查

日期：2026-10-26。状态：`PRECHECK_PASS / IMPLEMENTED`；非Gate结论。实施与客观验证见同目录 `plan-02-a04-p04-a04-p03-p04-s03-p03-a03-create-http.md`。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A03`。
- 输入基线：Gate 2冻结 API-04 `PLAN_VERSION_CREATE`、`PlanVersionInput`；A02事务型Owner和0188 append-only guards；API-01公共请求/错误合同；CR-PLAN-005受控V1代码目录。
- 前置任务：A02 Win11/隔离PG18合成Owner验收通过；Plan身份创建/读取及Outline当前批准来源Review链可用。
- 涉及模块：Plan API、Windows Plan组合根、Plan Application事务Owner；不改Solution/Review/Schema层。
- 涉及实体：Project、Plan、PlanVersion DRAFT及冻结PlanVersionInput下的WBS/Dependency/Milestone/固定来源引用。
- 涉及API：仅实现已冻结的`POST /api/v1/projects/{project_id}/plans/{plan_id}/versions`；不增路径、不改请求字段语义、不改API版本。
- 涉及权限：Origin/Session/CSRF预检；Owner事务内复验ProjectManager或ImplementationMember授权、有效License及Approved来源；不得只依赖HTTP预检。
- 验收标准：默认应用不挂路由；Windows显式受控模式才挂载；成功201响应含PlanVersion固定身份/版本号/状态并带no-store；缺失/重复幂等键、非法路径/请求/来源、错误角色、License拒绝按公共错误合同投影；相同Key重放原响应、冲突409；隔离Win11/PG18实际HTTP链写入完整快照且Audit/Receipt同事务；请求绝不含DB列/路径/Locator等内部字段。
- 风险：冻结Contract只概述PlanVersionInput语义，不能另造字段；以A02严格解析器接受的精确闭合JSON形状作为实现依据。OutputArtifact无Owner，非空`output_refs`维持失败关闭。不得令0188脱离Owner独立交付。
- 迁移/回滚：不新增Migration。回滚为撤下可选Router/组合接线并恢复Owner-only；A02/0188数据模型不变。
- 验证计划：Contract错误/响应测试；默认关闭与Windows显式组合模块导入；Win11隔离PG18真实HTTP组合，验证成功/重放/冲突/拒绝及审计；定向和完整后端回归、diff-check、Secret检查。

## 代码事实与选择

- API-04冻结表已定义PlanVersion创建路径及ProjectManager/ImplementationMember写角色；API-01规定Idempotency-Key，`create_plan.py`提供可复用的Origin/Session/CSRF/`read_body`/错误投影范式。
- A02的`PlanVersionCreateService`在同一个写事务再次校验Session、Project角色、License、来源、幂等回执和Audit，因此HTTP层只作早期身份/请求保护，不替代事务授权。
- `PlanVersionInput`对顶层和子对象键集合严格相等，Output refs明确失败关闭。HTTP应直接传递已解析JSON对象，不映射或丢弃字段。
- 本WBS不改变冻结Contract或Schema，暂不需新增CR；若实测发现只能通过破坏性改合同才能满足，则先按持续授权登记CR并保留原冻结内容。

## 结果

实施已完成并按进度记录中的合同、隔离PG和回归标准验收。Pilot、Gate 3、正式信任、多平台Release状态不因此改变。
