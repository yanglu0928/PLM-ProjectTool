# LIC-03-A01 TrustedTimeState ORM/Migration

- 日期：2026-09-24；结果：PASS；来源：Gate 2 冻结 DM-02/SC-01～03、ADR-006、`DEC-20260924-086`。
- Changed：部署级 `lic_trusted_time_states` 单例与 `lic_trusted_time_events` 不可变事件；时间严格前移、版本逐次加一、事件指针变化、历史不可 UPDATE/DELETE/TRUNCATE。首行允许空状态；完整性字段仅为对象型存储，不在本项确定算法。
- Files：`trusted_time_orm.py`、Alembic `20260924_0010`、注册/契约测试、`validation/lic-03-a01-trusted-time/verify.py`、本进度及版本说明。
- Migration：空库 up/down/re-up、已有用户数据升级、ORM drift=0、单例/形状/单调时间/版本/不可变负例、非空 downgrade 拒绝、含前移历史的 `pg_dump`/`pg_restore` 均 PASS。
- API：无新增或变更；Permission/Exception：无公开入口，约束失败关闭；真实 License 权限仍待后续服务接线。
- Tests：Windows 11 / Python 3.13 后端 132/132 PASS；PostgreSQL 18.6 隔离数据库迁移与恢复 PASS；后端 wheel 构建 PASS。Windows Server 2025、Debian 13 本项未运行。
- Known Issues：数据库存储约束不是完整性认证。`TrustedTimeStatePort` 必须用 expected_version 原子更新、生成/验证完整性元数据，并将回拨/损坏/冲突失败关闭且审计。生产签名/机器/产品/功能/时间判定、导入/激活尚未实现；不能据此宣称 License 有效或 Gate 3 通过。
- Next：LIC-03-A02 TrustedTimeStatePort 单调更新与完整性边界。
