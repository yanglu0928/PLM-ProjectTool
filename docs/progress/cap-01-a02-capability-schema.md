# CAP-01-A02：Capability Schema0091 / ORM

日期：2026-10-05。结论：`CAP_01_A02_CAPABILITY_SCHEMA_PASS`。下一项：`CAP-01-A03` 内部 Baseline/Draft Version 创建与来源验证 Owner。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A02
输入基线：冻结DM-05、SC-01/02/04、CR-CAP-001、DEC-831
前置任务：CAP-01-A01完成；Document/Evidence/Auth/Review表与迁移头0090存在
涉及模块：新增capability ORM/Migration；只以FK和deferred validator读取Document/Evidence当前事实
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem、DocumentRef、EvidenceRef
涉及API：无；API-04十二个Operation保持未挂载
涉及权限：Schema只允许初始ACTIVE Baseline和完整DRAFT Version；正式状态转换全部关闭
验收标准：空库/历史库升级、空历史降级重升、drift=0、完整GLOBAL来源成功、错误集合和非法状态失败、有历史拒降
风险：悬空来源、半版本、Project资料混入、Draft被误作APPROVED、降级删除历史
```

## 实现

新增 Schema0091 与五个 ORM 表，`source_collection_ref` 使用 CR-CAP-001 的精确 GLOBAL DocumentVersion 集合摘要。事务提交期重算声明计数、逐项 Document/Evidence 完整性、GLOBAL/AVAILABLE/ACTIVE/ELIGIBLE 当前事实和 Evidence-DocumentVersion 同源关系。初始数据库守卫只接受正式指针为空的 ACTIVE Baseline 与无 Review 的完整 DRAFT Version，所有更新、删除和清空失败关闭。

`migrations/env.py` 已登记 Capability metadata；迁移合同和 ORM inventory 更新到0091。开发 wheel 包含 capability 三个模块条目与迁移文件。无公开 API、生产挂载、依赖、外部网络、Secret 或客户数据变化。

## 验证证据

- Windows 11 / PostgreSQL 18.6：空库与已有平台数据升级、空 Capability 历史 `0091 -> 0090 -> 0091`、两次 Alembic drift、完整合成 GLOBAL 标准文档/Evidence、错误 source hash、非法正式指针、Owner 关闭与有历史拒降均通过；标记 `CAP_01_A02_CAPABILITY_SCHEMA_PASS`。
- 定向单元 8 项通过；补充 ORM inventory 后相关定向 11 项通过。
- 后端全量 2533 项通过、3 项既有条件跳过、0 失败。
- 开发 wheel `plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl` 共900项，SHA-256 `f2df5cbf900f438ff68728fe0e6b57b49de6d49a057bc4f0aba95d13b88737dc`；仅可安装性检查，不是最终发行包。
- `compileall` 通过，`git diff --check` 通过。

首次误用 `python -m pytest` 因测试环境未安装 pytest 而退出，随后按仓库实际 `unittest` 入口运行；第一次全量回归仅因历史 ORM inventory 未登记新增表出现1项失败，更新固定清单后完整重跑通过。两次均未作为通过证据，也未增加依赖。

## 兼容、升级与剩余边界

该增量仅为内部 `0090 -> 0091` 追加，不破坏冻结 `/api/v1`。无 Capability 历史可物理回滚；有历史时只允许向前修复。当前尚无受权创建 Owner、幂等/Audit、Review Subject、APPROVED 指针、HTTP、前端或生产组合；现有标准能力资料没有自动导入，合成数据不证明内容质量。Gate 3、正式信任、性能、Windows Server 2025当前链、Debian 13发行与可使用程序包仍未完成。
