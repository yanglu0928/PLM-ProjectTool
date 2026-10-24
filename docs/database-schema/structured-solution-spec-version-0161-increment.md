# 0161：闭锁 StructuredSolutionSpec 版本根

- 版本/来源：2026-10-12 / `20261012_0161`；Gate 2 DM-05、SC-01 `SOL-06`、SC-02 V-PRJ → DEC-1198/1199。迁移只追加在 `20261009_0160` 之后，不改冻结 Schema V1 或旧迁移。
- 表：`plm.sol_structured_specs` 的 `structured_solution_spec_id` 是不可变版本主键，`spec_series_id` 分组升版，`project_id` 强制 PROJECT；固定 `spec_type` 四选一、正 `version_no`、受控状态、32 字节指纹、前驱、Review 双引用及创建者/时间。唯一性包括版本/series/project 身份、series+版本号；前驱复合 FK 固定同 series/project/type。Project、创建者、Review FK 与非零 series、状态/时间等 CHECK 由数据库承担，两个索引支持 series 历史和项目类型筛选。
- 闭锁：INSERT/UPDATE/DELETE 与 TRUNCATE 均由专用触发器拒绝。该表目前没有 typed payload 与四类固定引用，不能生成真实 Spec 或被章节引用；未来必须先建立完整子集合/类型校验与受权 Owner，再以独立迁移开放受控 INSERT。既有 SectionVersion 0160 Guard 未修改。
- 升级/回滚：空库和已有 Project 数据可从 0160 升至 0161，均不回填/改写旧数据；仅 SOL-06 表为空时可降回 0160 并重新升级。任何非空历史都拒绝降级；不允许为了回滚清空生产历史。离线 downgrade 禁用。
- Windows 11/一次性 PostgreSQL 18.6 验证：空库升级与 drift、有数据升级与 Project 保留、空表降级重升、四类类型/版本号/指纹/Project FK/series 唯一/跨 Type 前驱约束负例、DML/TRUNCATE 闭锁、合成非空历史拒降和最终 drift 均通过。非空行仅在隔离测试库中临时停用 Owner 触发器以验证数据库约束，未开放生产写入口；测试集群停止并清理。后端全量 3601 通过、3 跳过、5612 子例，开发 wheel 通过。
- 未完成：四类 owned refs、类型化 payload、正式 Owner/HTTP/Windows、Trace `SOL-06` Owner、章节固定 Spec refs/VALIDATE、Review、正式账户/发行信任与 Gate3/Pilot/多平台验收均未通过。
