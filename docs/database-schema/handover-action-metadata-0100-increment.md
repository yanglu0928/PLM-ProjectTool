# Handover Action Metadata Schema 0100 增量

日期：2026-10-05。迁移：`20261005_0099 -> 20261005_0100`。

Schema0100仅允许OPEN/IN_PROGRESS Action在强锁推进时修改title、requested_input_spec、owner_ref、due_at、priority，并追加同状态事件；来源、action_type、创建事实和生命周期投影继续不可变。空修改失败关闭；存在同状态事件的历史拒绝降回0099。无新增表列、公开API或依赖。

Windows 11/PostgreSQL 18.6已验证assigned owner/PM部分更新、强ETag、无变化不写、权限、Audit回滚、License拒绝、同状态历史及有历史拒降。
