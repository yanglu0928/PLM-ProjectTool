# SOL-06-A11-P02：结构化专项内部列表读取

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 `SOL_SPEC_LIST` → A11-P01 全部不可变版本语义 → 本项。当前 Phase 2。
- 编码前检查：A09 创建、A10 详情、项目成员读权限与 0164 完整写入闭合均已通过。本项只新增 Solution 内部摘要分页、Repository 和 `SOL_STRUCTURED_SPEC_LIST` 锁定读策略；不开放 HTTP，不改 Schema、现有路径、写权限或 License 权益。验收为多版本稳定 keyset、项目成员、跨项目/失效 Session、损坏摘要失败关闭。
- Changed：增加不可变专项摘要与分页 DTO；Service 在有效 License、Session 和当前项目成员授权下列出全部版本，严格核对项目、降序边界、series/version 唯一、状态、指纹、Review 配对和时间。Repository 以 ProjectId + `structured_solution_spec_id DESC` 读取 Root/Payload，`before_spec_id` 做 keyset，缺 payload 或不一致摘要失败关闭。新增独立 `SOL_STRUCTURED_SPEC_LIST` 全项目成员锁定读策略。
- 验证：定向 15 项/790 子例通过；Windows 11 可弃 PostgreSQL 18.6 真实来源产生同 series v1/v2 后，以 page_size=1 两页读全且无重复，普通项目成员可读，跨项目与失效 Session 拒绝；创建 Repository/来源链回归通过。后端全量 `3638 passed, 3 skipped, 5710 subtests passed`。开发 wheel 1396 条目，SHA-256 `65adba214d085b48fe96d357b6f5ee4a52605f108714d9cd4cca63b4b81963b2`。首次 `pip wheel` 因测试 venv 未安装 pip 未产物，改用项目 setuptools build backend 成功，未改生产依赖。
- 兼容性/升级/回滚：无 Migration、公开 API、外部依赖或旧数据变化；未装配的内部读方法和新读策略可撤回，历史不动。Windows Server 2025/Debian 13 未实测，不能从 Win11 推定。
- 限制：当前 `before_spec_id` 只在内部边界传递，尚无防篡改/会话绑定的公开游标；HTTP、Windows 组合、页面和 Edge 仍待。摘要不证明来源现时有效或 Review 已通过。专项修订/验证/送审、OutputArtifact、章节六维、Gate 3/Pilot/正式 Release 仍未完成。
- Next：`SOL-06-A11-P03` 增加专项列表专用 HMAC 游标，绑定 family、Session、ProjectId 与 page_size，验证篡改/跨项目/跨会话/跨查询拒绝。
