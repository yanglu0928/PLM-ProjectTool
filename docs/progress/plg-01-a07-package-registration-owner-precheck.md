# PLG-01-A07：签名插件包元数据登记与验证结果原子Owner编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A07
- 适用变更：CR-PLG-005（路线纠正与Package metadata registration Owner）
- 前置：PLG-01-A01～A06 PASS_SCOPE_LIMITED；Gate 2基线不变
- 执行约束：仅GitHub hosted Windows Server 2025 runner的D盘临时环境；仅合成包、合成Ed25519 key及合成兼容策略；不在用户本机/C盘运行

## 单一目标

把经现有A06 Inspector验证的固定签名ZIP和受注入Compatibility Policy批准的Manifest，作为不可变Package记录及Manifest Operations/Dependencies/PASSED Verification证据原子写入0222既有Schema，并追加同事务Audit。为后续异步Import Job提供内部应用Owner，不开放HTTP或安装行为。

## 编码前检查

|检查|证据与结论|
|---|---|
|路线核查|A06由run 41582564698全13 jobs PASS_SCOPE_LIMITED关闭。Output P03已由run 41417503109完成；PLG A01～A06均已有结果。根据CR-PLG-004待办边界与API-03 PLUGIN_PACKAGE_IMPORT，当前进入A07。|
|冻结输入|API-03/DM-04/SC-01～03已有固定PluginPackage metadata、manifest operations/dependencies与verification evidence；不增Schema字段、API字段或产品Scope。|
|现有实现|A06 Inspector返回Validated archive/Manifest evidence；A05 resolver仅从包内公开manifest读取ACTIVE signer，当前清单为空；0222四表有fail-closed Owner trigger。|
|写入边界|A07唯一新增metadata registration Owner；使用同一个调用方UOW，Package+children+Verification+Audit全有或全无。SQL repository不得打开/提交transaction。|
|身份冲突|使用已有(plugin_id,version)唯一约束及transaction advisory lock；相同身份+相同archive SHA返回既有记录，不重复写Audit；相同身份+不同digest拒绝。|
|Migration 0223|仅安装INSERT Owner；表记录UPDATE/DELETE均拒绝，TRUNCATE拒绝保持；down恢复旧闭写触发器且不删除数据；验证空库/含历史库及Schema drift。|
|真实信任/兼容|测试只注入合成signer及compatibility policy。空默认公钥清单使生产包仍无法可信导入，且A07不注册生产组合。|
|数据存储|数据库不写ZIP正文或本机路径，仅保存固定签名/Hash/Manifest/声明/状态/验证摘要。后续安装需另行拥有经SHA-256重验的包字节。|
|验收|定向Owner事务/冲突/审计回滚测试；真实hosted PostgreSQL 18迁移与父子/Audit原子性、重复导入、不可变和downgrade保护；全后端/wheel及PR包链。|
|回滚|保留0223历史；空库可down；含数据时只回到闭写状态，禁止丢弃签名Package记录。|

## 实施文件范围

- 新增 plugin application package_registration.py
- 新增 plugin infrastructure package_registration_repository.py
- 增加Alembic revision 20261103_0223（down_revision 20261102_0222）
- 增加Owner单测及GitHub hosted PostgreSQL 18 migration/integration验证
- 更新迁移head/schema validation及CR/STATUS/CHANGELOG
- 新增验收结果文档

## 明确不做

不增加HTTP/Job路由、ZIP二进制落盘、安装/解压/启停/执行、公开trust root、包撤销或状态更新。签名/Manifest/兼容检测失败不会落任何Package记录；不发送外部AI或客户数据。
