# CR-OUT-014：OutputRequest取消HTTP接入显式Windows write composition

- 日期：2026-11-04
- 状态：P18编码前检查 PASS_WITH_LIMITATION；实施中
- 来源：CR-OUT-012/P16 opt-in取消HTTP、CR-OUT-013/P17 PostgreSQL 18事务验收
- 基线：遵守冻结API Contract V1的OUTPUT_REQUEST_CANCEL路径、角色、请求与响应；不改架构、Schema、Migration或API合同

## 问题与证据

P17证明OutputRequest/OUTPUT_GENERATE Job取消Owner的PG18事务边界，但当前取消HTTP只存在于modules/output/api/cancel_request.py，entrypoints/api.py:create_app没有对应可选Router参数，entrypoints/production_login.py也没有构造或挂载取消服务。生产登录/默认app与Windows显式write模式均不能通过HTTP调用该能力。

现有Windows生产组合已具有同一UOW runtime、SessionService、Origin policy、License guard、AuditService及Idempotency receipts，并在include_secret_write控制的显式write模式装载写路由。现有SqlAlchemyProjectWriteAccess可在同事务核验Session/CSRF；ProjectAuthorizationService目前只有OUTPUT_REQUEST_LIST只读策略，需增加只允许ProjectManager的OUTPUT_REQUEST_CANCEL操作，并在Output Cancel Access中另行允许请求创建者。P16冻结控制要求creator或ProjectManager，不能误将ImplementationMember等普通写角色授权取消。

## 实施方案

P18仅接入既有单个取消端点：添加Output Cancel生产Access/Windows composition factory；以同UOW Session身份、创建者例外、ProjectManager强授权、License guard、Output与Jobs repository、幂等收据及Audit构造既有Service；向create_app增加默认None的可选router并仅在Windows显式write composition传入。默认login、平台只读模式不挂载；不改变路由合同、不开放其它Output API。

如授权policy code需加入ProjectAuthorization，应保持OUTPUT_REQUEST_CANCEL只限ProjectManager，并让创建者分支按真实OutputRequest.requested_by精确比较；授权失败仍按RESOURCE_NOT_FOUND失败关闭。只触碰本任务的Output取消装配和必要授权，不接Output Create/Read/List或Worker。

## 影响、风险、回滚

- 风险：write composition的调用范围广；若错误挂载到普通或只读模式会提前暴露写API。通过默认None、只在include_secret_write设置Router，并测试各模式404/目标模式匹配来隔离。
- 风险：ProjectManager与创建者授权组合或项目成员撤销时的语义误配。以冻结契约为准；PG18/HTTP测试覆盖owner、manager、implementation member、跨Project、被禁Session、缺License、CSRF/Origin、If-Match及重放。
- 无数据迁移。回滚为移除新工厂、access/policy、app参数和write组合注入；冻结URL保持未默认暴露。
- 正式信任缺口仍由当前启动门禁关闭；Hosted synthetic组合不得冒充Win11真实信任或Pilot。

## 验收计划

1. backend定向单元/HTTP集成测试；验证default/readonly router不挂载，显式write composition注入后才可调用。
2. GitHub hosted PG18.6合成Session/Project/License实例，实际触发HTTP端点并断言creator与ProjectManager授权、其他角色/跨项目拒绝及持久审计/幂等。
3. backend全量测试/wheel与完整Cloud parent/A17/A34/A35/A50链；secret扫描；仅hosted runner D盘临时区执行。
4. 结果仅按证据记为PASS_SCOPE_LIMITED；真实Windows 11、正式License公钥/来源、服务账户ACL/TLS及Output Worker仍分别追踪。

## 编码前检查结论

PASS_WITH_LIMITATION。证据已确认API router与默认App均解耦，Windows显式write模式具备Session/Origin/License/Audit/UOW/幂等基础依赖，Output/Jobs P17 repository已通过PG18.6合成事务验收。缺口是取消Access生产实现、ProjectManager policy和Router组合。可按上方案编码；无Schema/Migration和冻结合同变更。

## 实施偏差记录（hosted run 41805787695，首次验收）

- 2026-11-04，代码提交 `7e540bfd3433a1df431dc37d32e8d059c3e7528a` 的 hosted run [41805787695](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41805787695) 未通过：后端全量测试执行 4,013 项，其中 1 项新路由装配单测失败、1 项既有 ProductionLogin 组合合同测试错误；随后 key ceremony、wheel 与依赖的父包验收被工作流跳过。Frontend/build、Python/PG sidecar rebuild、A17 harness syntax 与 A50 Edge job均成功。
- 当前根因尚在定位；日志定位到显式 App 路由断言未找到 POST，以及基线 ProductionLogin 无写模式启动抛出 `ProductionLoginStartupError`。在定位前不判定为产品代码缺陷或单纯测试误报。
- 影响：P18仍未通过；没有 Gate/Pilot/Release 状态变化。未产生客户数据或生产副作用。
- 处理：先基于失败栈检查App挂载方式与显式/默认组合初始化，再作最小修复；保持默认路由关闭、显式写组合才开放。修复后重跑完整 hosted workflow；若失败再次记录后再改。
