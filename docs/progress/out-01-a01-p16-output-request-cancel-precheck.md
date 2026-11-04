# OUT-01-A01-P16：OutputRequest 取消 Owner/API 编码前检查

- 日期：2026-11-04
- 状态：编码前检查通过；按 CR-OUT-012 开始实施
- Phase/WBS：Phase 2 Platform Core / OUT-01-A01-P16
- 执行环境：仅通过 GitHub API 查看源码；后续程序与测试仅在 GitHub hosted runner 执行，不在用户本机/C盘运行
- 输入：冻结 API Contract V1/API-03、API-01；CR-OUT-012；P12 Create Owner与Jobs Output enqueue；Jobs Lease/Cancel/Idempotency/Audit规则

## P16 唯一目标

实现冻结 `OUTPUT_REQUEST_CANCEL` 单操作的可注入Owner和opt-in POST：将授权的 OutputRequest 与其唯一绑定 OUTPUT_GENERATE Job 按相同事务取消/请求取消，并保留 Audit、幂等和强 If-Match语义。默认应用与正式组合继续不挂载。

## 最后编码前检查

- 当前源码无Output完成/失败终态Worker Owner、无Output cancel Owner；故无现存跨实体锁序。依CR-OUT-012，事务锁序明确固定为 OutputRequest 行 → Job 行 → active Lease/Attempt；未来Output Worker须遵循同一顺序。运行中只记录取消请求，不宣称已终止进程。
- 复用Jobs现有取消事实/状态语义与fencing约束，但不复用JobId HTTP dispatcher（它以Job为路径资源且关闭hint UOW后另启Owner UOW）。Output模块不得读写Jobs ORM；通过Jobs application transaction-scoped端口交互，Owner必须对Job owner/type/scope/project/payload/source绑定重验。
- Output强If-Match比较数据库锁定并刷新后的 OutputRequest.lock_version；IdempotencyScope为 actor+project+V1_OUTPUT_REQUEST_CANCEL，指纹绑定reason和expected_version。重放先做当前授权和实际资源绑定验证，再按同Key首次引用回读结果；不得因当前lock_version变化误拒精确重试。
- 创建者与ProjectManager按冻结API-03授权；其它成员/管理员不能仅因Job可读或有广泛项目角色取得取消权。Project/Session/CSRF/License在实际事务内复验；跨项目、丢失/不匹配Job绑定及状态不一致安全失败。
- 更新 OutputRequest request_state/lock_version、Job cancellation facts、Audit及幂等receipt同一UOW；任何异常回滚。reason严格限制为唯一JSON字段、1～1024个trimmed无控制字符；不接受外部状态、JobId、路径或正文。
- 不改API Contract/ORM/Schema/Migration，除非Hosted实现发现当前Idempotency/Audit机制确实不足；如需扩展则先更新CR并记录迁移/回滚/验收方案。新Router opt-in，不装入默认/正式应用。
- 验收需新增单元/HTTP/PostgreSQL 18隔离实测：两Project隔离、creator/manager与拒绝角色、PENDING与RUNNING/终态规则、Output与Job绑定、ETag陈旧竞争、同Key并发精确重放、Audit故障全回滚；通过GitHub托管全量后端/wheel、PG18以及父包/A17/A34/A35/A50既有回归后才可标PASS_SCOPE_LIMITED。
- Secrets检查限测试桩/文档差异扫描；不读取本机秘钥或客户目录，不向任何AI供应商发送材料；不运行本机代码与测试。

## 结论

P15/P16的变更与实现范围均有CR-OUT-012先行记录。锁序偏差已在编码前写入CR：没有现存Output终态Owner可复用，改为固定的OutputRequest→Job→Lease/Attempt顺序。范围和前置已清楚，进入P16实现；未声明任何代码验收、Gate、Pilot或Release通过。
