# AUT-04-A12-P06-A04-P02-A02：历史密码 detached source

## 编码前检查

- 当前 Phase：2 Platform Core；单一任务：reset/change 历史 first 的精确 Credential 源提取、事务外真实 KDF、写事务来源重新比较接口。
- 输入：冻结64cdf09、CR-AUT007/008、0049；前置 readonly receipt hint A01 已通过并同步38cdb59。
- 模块 auth，既有 immutable first/Credential；无 Schema、Migration、API、依赖、授权或算法变更；密码 Service 编排另项，不提前声称性能修复。
- 取源仍校验完整 first 相等、精确 User/ID/version、原 changedBy/time/mustChangeFlag 与固定 Scrypt profile；仅隐藏 repr 的请求内 PasswordHashResult 副本，无 ORM/Session/权限缓存。
- verify_source 不接收 transaction、不读数据库；strict source/profile/password/输出 bool，未知固定拒绝；原 verify 接口兼容委托。
- require_source 再次取真实完整 first 与 Credential，比较来源，不计算 KDF、不授予权限；后续原当前 Session/CSRF/Admin/License 和 reserve/final 全保留。
- 风险：source 与 first 错配、可变 profile、闭事务引用、异常泄密、旧接口回归；单元+实际PG真实reset/change/后续凭据变化/READ ONLY与独立锁/九表无写验证，全量回归。
- 回滚：撤新接口/恢复原 verify 实现，保留历史与原冻结，无数据库升级。验收待执行；CR/Gate 性能 FAIL 保留。

## 执行结果

- PASS，仅 exact historical source 接口：1409 tests 无失败（2既有跳过），副本/隐藏repr、fresh重取/错误源、strict KDF bool/异常、坏profile/输入、原verify精确委托通过。
- 实际PG执行真实 reset Credential2→change Credential3→later change Credential4；READ ONLY 提取事务已退出后，原reset临时/before临时/after正常密码真实固定Scrypt全部匹配，最新密码对这些历史源全部 false。
- 六次真实KDF调用期间，独立PG连接可取 deployment/User/全部目标Credential锁；无DB事务引用。READ ONLY 最后full-first/source复核不调用KDF，错误role/source、伪造trace首次结果均拒绝，九表快照不变。
- 原 reset 原子全链（当前权/并发/故障回滚/丢提交回执/soleAdmin实际change-history）和 dualScope publication 回归通过；License 正向合成，非生产信任证明。
- wheel 750773 bytes，SHA-256 `b52a27210f31e39e37a2936e0ea8628be0ae9ecee24dd6611e4974bab737e2af`；内部构建，不是可用安装包、不上传。
- Files：两项 Result Repository、historical source unit、actual验证与本记录/DEC329/CR008/STATUS/CHANGELOG。Migration/API/依赖：无，0049兼容，未执行生产升级。
- Known Issues：Service 尚未调用新接口，原历史KDF锁段仍存在；本轮性能未重跑，上轮FAIL保持；Gate3/CR008开放。
- Next：A03 reset historical replay 编排；readonly hint+actual first/source 在短预认证UOW内获取，KDF在关闭事务后有界执行，原write UOW最新授权/reserve完整结果source复核；只读miss后first竞争出现须有界重新准备、不锁内KDF，不免当前权。
