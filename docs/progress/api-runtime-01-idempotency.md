# API-RUNTIME-01：通用持久幂等收据

- 日期：2026-09-25；结果：PASS（基础设施和 PostgreSQL 18.6 验证；不代表注销或其他命令已接线）。
- 当前Phase：Phase 2 Platform Core；当前WBS：API-RUNTIME-01。
- 输入基线：Gate 2 冻结 API-01 幂等合同、DB Schema V1、CR-API-001；前置 PostgreSQL/Alembic 基础 PASS。
- 涉及模块：Platform Application/Infrastructure；实体：新增 `plm.plt_idempotency_receipts`；API：无公开路由；权限：由未来调用方先验证 Session/License/资源权限，收据本身不授予权限。
- 验收标准：actor/project/带 V1 版本的 operation/Key 摘要作为数据库唯一范围；规范化 payload SHA-256，不存原始 Key/正文；同载荷返回原结果引用与状态，不同载荷 409；reserve、业务操作、Audit、complete 同事务；空库及有数据升级、空表降级、非空降级拒绝、并发单赢家、失败回滚和已完成不可变。
- 风险：当前基础设施不能替业务命令完成权限/审计和结果重建；误提交 PENDING 后安全拒绝重放，须走受控诊断/恢复，不自动重做副作用。ProjectId 未设外键，调用方须使用已授权资源归属；收据暂无自动过期/清理，Retention 需另行验收。

Changed：新增通用收据 ORM、Alembic `20260925_0015`、范围/结果对象、规范化 JSON 指纹和 PostgreSQL reserve/complete 仓储。唯一约束使用 `NULLS NOT DISTINCT`，使无 Project 的部署级命令仍可并发去重。已完成收据由触发器禁止 UPDATE/DELETE；旧配置专用收据表保持不变。

Files：`idempotency.py`、`idempotency_orm.py`、`idempotency_receipts.py`、Migration `0015`、迁移注册/合同/单元测试、一次性 PostgreSQL 验证、CR/决策/状态/版本说明。Migration：新增，旧数据无需转换；升级前备份数据库；有收据时 downgrade 拒绝。API：无新公开路由或 Breaking Change。

Tests：Windows 11/Python 3.13 后端 324/324 PASS；PostgreSQL 18.6 一次性数据库空表 up/down、有配置数据升级、Alembic check 无差异、部署/项目隔离、同 key 重放/不同 payload 冲突、事务回滚、PENDING 失败关闭、并发单赢家、Completed 不可变和非空 downgrade 拒绝 PASS；临时库已删除，PostgreSQL 已停止；wheel 构建 PASS。Windows Server 2025、Debian 13 本项未验证。

Known Issues：注销还需要在已撤销 Session 的安全重试场景中建立可验证的收据关联，不能绕过 Session/CSRF 把任意旧 Cookie 当授权；`PLT-02-A07`、POC-03 质量和 Gate 3/UAT 均未关闭。

Next：实现 `AUT-03-A10` 注销 HTTP，同事务使用新收据保存安全结果引用，并验证首次成功、同 Key 重放/冲突、旧 Session 不获新权限、Cookie 清除与 Audit。
