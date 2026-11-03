# CR-PLG-008：PluginInstallation按操作原子启用与版本切换

- 日期：2026-11-04
- 状态：编码前决定已登记；按持续自主执行授权实施，须以托管证据验收
- WBS：PLG-02-A03
- 关联：CR-PLG-007、冻结Data Model V1、SC-01/SC-02、Gate 2 API Contract V1

## 原因

PLG-02-A02只建立经核验的初始Installation事实。冻结模型还要求同一plugin_id的每个operation至多由一个Installation启用，版本切换必须原子且可审计并保留Installation历史。目前Owner关闭表及空的启停业务路径阻塞后续Output执行前的许可检查。

## 决定与范围

- 新增内部Owner，接收Installation ID、非空操作集合、actor/trace及目标M-DEP lock_version。只允许Manifest声明的操作子集。
- PostgreSQL事务先取得插件级锁，再锁定目标Package/Installation、当前启用行及同plugin操作冲突的Installations。目标必须是VERIFIED且未撤销Package、状态为INSTALLED/DISABLED/ENABLED，且最新COMPATIBLE runtime snapshot与Installation当前核验快照一致。
- 一次事务把目标操作集合切到目标Installation、从旧Installation撤下冲突操作；若旧安装不再拥有其他启用操作则将其状态降为DISABLED，仍有操作则保持ENABLED。目标Installation置ENABLED；固定identity/安装事实不改，M-DEP lock_version单调递增。
- 所有行变化与对应Audit在同一Unit of Work内提交或回滚。Exact state replay为无写入幂等；过期目标lock_version拒绝；PK/Package/Manifest FK及数据库操作唯一索引保持最终保护。
- 只允许本内部Owner操作状态与owned enabled operation记录。不开HTTP API、不接默认组合、不安装文件、不改变Publisher trust、不启动插件子进程、不使Output Create可用。
- Migration `20261104_0227`把0226关闭守卫升级为受限Owner标记下的最小操作：Installation仅允许状态/Actor/时间/lock_version规定变更；EnabledOperation仅允许Owner插入/删除；RuntimeValidation仍只追加。继续拒绝TRUNCATE，任何Owner标记外的写入均拒绝。Down仅当目标表无Installation/EnabledOperation/RuntimeValidation记录时回退。
- 无冻结Data Model/API或外部依赖变化。按操作记录历史由追加Audit和不可覆盖的Installation行追溯；owned EnabledOperation表只表示当前状态。真实DB身份隔离和宿主执行信任不由本项替代。

## 风险、迁移与验证

- 主要风险为并发版本切换、操作集合部分重叠、Audit失败和runtime snapshot过期；由插件级advisory lock、行锁、lock_version、唯一索引、同事务Audit及PG18并发/回滚反例覆盖。
- 迁移向前增加revision，不改既有行或冻结表字段。Rollback只有目标事实表全空才允许；存在任何安装/启用/运行时验证历史均失败关闭。
- 用仅合成包和安装事实的GitHub hosted Windows runner D盘临时PG18/单测/全链回归验证。用户本机不运行项目代码或测试；客户数据和外部API调用为0。
- 测试失败或发现与冻结语义不兼容时，先补本CR偏差记录，再改代码。仅PASS_SCOPE_LIMITED；不宣称实际插件执行、Windows 11安装、Gate、Pilot或正式Release通过。
