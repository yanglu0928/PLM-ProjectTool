# AUT-04-A10-P01 User名称修改

## 编码前检查

- 当前Phase：Phase 2 Platform Core；Gate 2冻结，Gate 3未通过。
- 当前WBS：AUT-04-A10-P01，内部名称修改一个问题；HTTP和Windows装配另项。
- 输入基线：64cdf09、冻结DM-02 User、SC-02唯一性/lock_version、API-02 AUTH_USER_PATCH；当前0046及AUT-04-A09创建链。
- 前置任务：User安全读取/当前Admin-CSRF策略/LicenseGuard/Audit/创建历史已实现；本任务不依赖未完成正式发行材料。
- 涉及模块/实体：Auth/User；Audit只用原Port；不改Credential、Session、首次创建结果。
- 涉及API：冻结PATCH的内部服务；本轮不开放HTTP。
- 涉及权限：当前ENABLED DeploymentAdmin真实Session-CSRF，License前后检查。
- 验收标准：NFC/trim/casefold唯一含DISABLED；版本先检查再判无变化；修改一次版本+1/同事务Audit；异常回滚；保持密码、角色、状态和首次创建历史；真实PostgreSQL竞争/拒绝无写。
- 风险：登录名改变，旧名称不再指向该用户，可能由新身份重新占用；无永久别名承诺。Admin先锁Session/actor再锁target可能死锁，异常安全回滚不冒充性能通过。原Guard独立事务，只证明前后检查而非业务事务License锁。

## 选择、迁移及回滚

DEC-20260927-299：允许完整名称变化，不以仅大小写变化替代冻结需求。目标可以DISABLED但不改变状态。既有display/canonical不一致拒绝，不静默修复。No-op不提交/不Audit/不加版本；旧版本即使同名仍冲突。变更只写名称、updated_by/at、lock_version；不添加Schema/依赖/权限/别名。保留原冻结提交与0046首次结果。

未知提交确认不得盲重试；读取当前版本确认事实，再用新版本提交。回滚撤新服务入口，保留历史和现有数据库；不反向覆盖已修改名称。名称更新的审计只记录固定动作、目标和状态，不存用户名正文。

## 验证状态

INTERNAL_PASS（Windows 11/隔离PostgreSQL18）；不是完整AUTH_USER_PATCH或发行验收。

- Changed/Files：Auth新增`application/user_name_patch.py`内部当前Admin命令及`infrastructure/user_name_patch_repository.py`条件更新；新增7项unit和实际PG验收脚本。
- Tests：后端1312项无失败，2项既有符号链接权限场景跳过；实际PG名称/canonical、新旧登录查找、禁用名称唯一、同版本双请求一胜一冲突、no-op及stale、权限/CSRF/缺目标/License拒绝六表无写；修改不改Credential/Session/receipt/首次结果，原创建密码重放仍首View。
- Exceptions：实际Audit INSERT后故障、末尾License关闭和同事务真实Session撤销皆六表完整回滚。初轮撤销夹具缺revoke_reason和lock_version增量被原约束拒绝；按既有Session规则修正夹具并重跑通过，生产约束未放宽。不一致名称源静态拒绝，无修复伪装。
- Migration/API：沿0046，无Schema/migration/依赖/权限变化；冻结PATCH内部增量，不挂HTTP，不改原基线。
- Build：开发wheel705209字节，SHA256 `e2907b3ce2fa05da89054af15d860cac794ca6b7507a4a97f6653cb1a8a26831`；不是安装包，不提交本地wheel。
- Regression：原双Scope空/260行实际文件发布、撤权/取消/过期/License/身份及写后故障回滚、实际锁竞争回归通过；未重跑全部历史Windows脚本。
- Known Issues：正向License合成；未验证真实死锁/20并发性能/提交确认恢复HTTP、正式信任供给、Windows组合、三平台、界面或安装包；Gate3不关闭。
- Next：AUT-04-A10-P02可选严格User名称PATCH HTTP，当前Session-CSRF/Origin/If-Match/静态错误/安全View；之后Windows write接线。
