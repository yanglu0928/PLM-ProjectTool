# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A03：PlanVersion DRAFT 创建 HTTP

日期：2026-10-26。状态：`PASS_INTERNAL_WIN11_PG18_SYNTHETIC`；非Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A03`。
- 输入基线：冻结API-04 `PLAN_VERSION_CREATE`/`PlanVersionInput`、API-01公共请求合同；A02原子Owner/0188 guards；CR-PLAN-005闭合代码值。
- 前置任务：A02事务型Owner在Win11隔离PostgreSQL 18.6端到端通过。
- 涉及模块：Plan API、Windows PlanVersion组合根、通用FastAPI挂载点；不改Schema/ORM或其它业务模块。
- 涉及实体：PlanVersion DRAFT及其WBS/依赖/里程碑/固定来源完整快照。
- 涉及API：冻结的 `POST /api/v1/projects/{project_id}/plans/{plan_id}/versions`，未增加路径或Breaking字段。
- 涉及权限：HTTP Origin、Session、CSRF；Application Owner内二次校验ProjectManager/ImplementationMember、License、Project/Approved来源及持久幂等。
- 验收标准：默认应用不挂载；显式Windows组合挂载；成功响应固定身份、版本号、DRAFT状态、时间、Location和no-store；非法请求/无效来源/不支持Output refs/幂等冲突安全映射；PG18真实HTTP产生持久完整快照、同Key重放首个data、改载荷冲突及拒绝路径零写入。
- 风险：完整WBS JSON远大于Plan身份创建请求；不应受既有Plan公共`read_body`默认128KiB意外限制。新Endpoint使用明确8MiB上限，仍保持硬边界及流式清零，不改变既有接口的上限。
- 迁移/回滚：无Migration；回滚为移除可选HTTP组合挂载，保留内部Owner和Schema。

## 实施结果

- 新增严格HTTP边界：Origin、Session/CSRF、单一Idempotency-Key、无query、规范UUID、有限JSON；原始业务对象直接传给严格Owner解析器，不丢字段。
- 成功响应只投影PlanVersion固定ID、Project/Plan ID、版本号、DRAFT和UTC时间；`Location`指向固定版本；设置`Cache-Control: no-store`。
- 新增Windows显式组合及FastAPI可选挂载参数；默认应用未挂载该路径。
- API-01常见错误投影已覆盖无效Session/CSRF、项目权限/来源、License、幂等冲突、输入拒绝及服务不可用；不向客户端输出异常或数据库字段。
- 为大体量冻结PlanVersion输入增加Endpoint专属8MiB上限，既有Plan API仍使用原128KiB默认上限。
- 沿用A02的真实PG合成验收脚本增加真实HTTP组合：Windows组合根、Session/CSRF、成功持久化、原响应data重放、Key载荷冲突，以及非空Output refs 422且数据库计数不变。

## 验证

- Contract + Owner定向：18 passed、866 subtests passed。
- Win11隔离PostgreSQL 18.6端到端：Owner完整快照/授权与来源、Audit失败原子回滚与恢复、并发版本号，及Windows HTTP真实创建/同Key重放/冲突/Output失败关闭均PASS；验证器exit 0。
- 完整后端回归：4128 passed、3 skipped、6174 subtests passed（66.34s）；改动文件`compileall`及`git diff --check`通过。
- Secret检查：变更的验证器与API实现无凭据、私钥或常量Token值。
- 测试运行时的pgvector 0.8.6 Windows二进制为非官方测试构建，仅位于项目外隔离运行目录；不纳入源码、安装包或客户环境。PostgreSQL 18.6 EDB binary ZIP仅用作本机验证，非正式发行装配结论。

## 交付边界

- Migration：无。冻结API合同无Breaking变化。
- 无前端页面、版本读取/列表、PlanVersion Validate/Review或OutputArtifact；分别留待后续WBS。
- 此项只证明Windows 11合成PG环境与合成License/用户组合，不证明正式信任、真实客户、Windows Server 2025、Debian 13、Gate 3、Pilot或正式Release。
- `0188` append-only guards和PlanVersion Owner须同一受控交付单元，禁止单独部署0188。

## 文件

- `apps/backend/src/plm_assistant/modules/plan/api/create_plan_version.py`
- `apps/backend/src/plm_assistant/modules/plan/api/_request.py`
- `apps/backend/src/plm_assistant/entrypoints/windows_plan_version.py`
- `apps/backend/src/plm_assistant/entrypoints/api.py`
- `apps/backend/tests/contract/test_plan_version_create_api.py`
- `validation/plan-02-a04-p03-owner-transaction-pg/verify.py`
- `STATUS.md`
- `CHANGELOG.md`
