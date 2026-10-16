# Audit取消首次版本增量

2026-09-27 / CR-JOB-004 / JOB-02-A03，原冻结64cdf09保留。新增Audit owned aud_export_cancel_versions：audit_event_id UUID主键/FK aud_events、lock_version bigint非负且不可空。原Audit事件保唯一状态/changed/Scope/project/actor/Job事实，不复制原因/Secret/payload/Lease/完整JobView。

ORM export_orm.cancel_versions与Migration0044一致；真实受理的USER取消请求/检查事件才可插入，行只追加，任何update/delete/truncate拒绝，含行downgrade拒绝并保head。原Audit历史不回填未知版本。实际锁定Jobs owned事实供给version，客户端不能传结果version，expected_version只用于前置并发比较。

新JobId取消同事务Job/Audit/receipt/版本快照原子，旧export调用与旧收据version=None兼容；原收据重放当前授权后返回首次state+首次version，不与当前Worker确认版本拼接。未来HTTP要求非None强ETag，不把旧None猜成0或当前值。

升级：人工备份/维护停止API Worker后0044，无本轮生产操作；空/有数据十表保持、ORM parity、非法与不可变保护/含数据降级拒绝、实际十一表回滚已验。无新增权限/角色/依赖；全Scope/正式材料/性能/Gate未关闭。
