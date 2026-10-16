# SUR-01-A02：Survey 定义 Schema/ORM 基础

日期：2026-10-06

状态：`SUR_01_A02_DEFINITION_SCHEMA_PASS`

## 完成内容

- 新增 `survey` 模块及 SRV-01/SRV-02 六张 ORM 表。
- 新增 Alembic `20261006_0103`，从 0102 安全升级；有业务历史时拒绝降级。
- 使用真实外键和受控 `source_kind` 固定 Handover、Capability、TEMPLATE DocumentVersion 与
  人工来源，保持 Project/Scope/版本可追溯。
- 以延迟完整性触发器验证声明计数、问题来源、选择题选项、当前批准来源和目标部门。
- Owner 尚未实现时关闭修改、删除和清空入口；没有导入客户资料，也没有形成客户确认事实。

## 偏差与处理

全量回归首轮仅发现已有 ORM 元数据清单是硬编码集合，未登记六张新表。该清单按精确表名更新，
未放宽断言；随后完整重跑通过。Alembic 仍报告既有 pgvector operator class 与 computed default
比较警告，本迁移未引入新 drift。

## 验证结果

- Survey/Migration 定向测试：8/8 PASS。
- Windows 11 / PostgreSQL 18.6 真实迁移与约束验证：PASS，含新增的选择题无选项负例。
- 后端全量：2783 PASS / 3 SKIP / 0 FAIL。
- Wheel 构建与内容检查：1017 个条目，SHA-256
  `b397d565ee4c26ee41d01b4800cb8117456efcab1bc379b31868de4a44f0785e`。

## 下一项

`SUR-01-A03-P01`：实现 ProjectManager 受权的 Survey identity 创建 Owner，接 Project/License/Audit/
持久幂等，仍不创建 SurveyVersion 或开放 HTTP。
