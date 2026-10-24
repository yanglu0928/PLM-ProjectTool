# SOL-06-A02：专项规格闭锁版本根

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 DM-05/SC-01/02 → DEC-1198/1199 → `20261012_0161` → 本项；下一项四类固定引用。
- Changed：新增 `StructuredSolutionSpecRow` 和 0161 Alembic 迁移，确立 PROJECT 不可变版本身份、同 series/project/type 前驱、四类 `spec_type`、Review 双引用和全 DML/TRUNCATE 闭锁；更新迁移 head/ORM inventory 测试。无公开 API、权限、依赖或 Section 0160 修改。
- Verification：Win11 可弃 PostgreSQL 18.6 空/有数据升级、空历史降级重升、非空拒降、约束和 DML 负例、Schema drift 脚本退出 0；初次全量回归仅因迁移 head 与 ORM 清单未更新而失败 2 项，补齐清单后定向 7 通过，全量 3601 通过/3 跳过/5612 子例；开发 wheel 构建通过。隔离数据库内的非空历史为合成测试数据，不代表客户正式专项。
- Risk/rollback：根表写入仍闭锁，不能因为 Schema 存在就标 SOL-06 可用。只有空表可降级；已有历史必须保留并升级修复。四类引用、typed payload、受权 Owner、HTTP/Windows、Trace 与 Section VALIDATE/Review 均待；Gate3/Pilot/发行未放行，Server2025 未实测，Debian13 实机按指令跳过。
