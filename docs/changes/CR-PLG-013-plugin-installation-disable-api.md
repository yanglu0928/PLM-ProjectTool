# CR-PLG-013：PLUGIN_DISABLE受控HTTP命令

- 日期：2026-11-04
- 状态：已批准，PLG-02-A08编码中
- WBS：PLG-02-A08
- 依据：API Contract V1 的 `PLUGIN_DISABLE`；PLG-02-A06 Owner；PLG-02-A07 Installation GET
- 优先级：在安装读取之后提供一个受控、可审计的管理停用入口
- 基线修订：不改变API Contract V1；为保证冻结I标记“同键同请求返回首次结果”，在Schema V1上增加一个向后兼容的追加式命令结果表，作为正式增量Migration 0230。保留Gate 2原冻结提交及现有0229历史。

## 变更原因

冻结API要求 `POST /api/v1/admin/plugins/installations/{installation_id}:disable`，控制包含有效Session、License、CSRF、Idempotency-Key、If-Match与Audit。内部Owner已能同事务撤销所有启用操作，但没有HTTP边界、真实身份装配和可重放的首次响应快照。没有持久结果快照时，重试会遇到旧If-Match，不能满足幂等合同。

## 决定与范围

实现单一人工停用HTTP命令：空请求体、无query、真实Cookie Session与CSRF/Origin、License及DeploymentAdmin复验、强If-Match、Idempotency-Key；复用A06 Owner，在业务变更、Audit、只读结果快照与Idempotency Receipt同一PostgreSQL事务完成。精确重放返回已保存的首次结果；同key异请求返回幂等冲突。只由显式Production Platform Write组合挂载，默认登录、Read和Write Trace组合均不挂载。

新增最小不可变 `plg_disable_results` 结果记录，链接installation、actor/trace、expected/result lock version、DISABLED及changed语义；不复制包正文/Manifest/环境。API仍不触发物理卸载、安装器或插件执行，不修改冻结API字段/路径/角色/错误语义。

## 风险、迁移与回滚

新增表与插件Owner写入Guard是本CR对Schema V1的最小兼容增量。空库升迁移、旧库有数据升级、down/up与结果留存守卫均托管验收；降级时只允许在无A08结果记录时删除新表，有结果时失败关闭以保留命令历史。代码回滚可撤下HTTP组合；不可静默删除已产生的命令结果。失败的业务事务必须同时回滚Owner操作、Audit、结果和Receipt。

## 验收计划与限制

在GitHub hosted Windows runner 的D盘临时区执行后端全量/wheel、前端/build、Migration空库/有数据升降、PG18合成真实身份/License/HTTP/幂等首调与重放/同键异载荷/缺If-Match/CSRF/锁冲突/Audit失败回滚、clean parent、A17/A34/A35/A50全链。源代码和项目测试不得在用户本机/C盘运行。最高为`PASS_SCOPE_LIMITED`；不表示Windows 11实机、正式安装信任、Pilot、Gate或Release通过。正式公钥/License、服务账户凭据、ACL/TLS及真实安装器仍是独立阻断项。
