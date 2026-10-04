# Handover Version Owner Schema 0097 增量

日期：2026-10-05。迁移：`20261005_0096 -> 20261005_0097`。范围：HND-02 DRAFT Version 创建所需的 HND-01 锁版本推进。

Schema0097 不新增表列。它把 0096 的全关闭 Analysis 更新守卫收窄为唯一允许形态：同一 ACTIVE identity 的不可变字段、状态及空正式指针保持不变，`updated_by` 必填，`updated_at` 单调，`lock_version` 精确加一。Version、Item 与 owned rows 仍只允许初始插入，更新、删除和 truncate 继续拒绝。

该转换用于强 ETag 下创建完整不可变 DRAFT Version；应用 Owner 还要求当前 ProjectManager/ImplementationMember、Session/CSRF、License、固定来源和无 `IN_REVIEW` Version。空 Version 历史可降回0096；存在任一 Version 时拒绝降级并要求向前修复或恢复备份。离线 downgrade 继续失败关闭。

Windows 11/PostgreSQL 18.6 验证覆盖空历史降升、ORM drift、三版真实创建/锁推进/supersedes、非法输入、审计回滚与历史拒降；旧0096 Schema验证在0097下重新通过。
