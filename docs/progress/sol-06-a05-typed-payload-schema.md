# SOL-06-A05：闭锁类型化 payload Schema

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 DM-05/SC-01 → DEC-1201 → 0161 Root/0162 refs → 0163 payload → 本项。
- Changed：新增单一 owned `sol_spec_payloads` ORM/0163 迁移与迁移 head/元数据清单测试，固定 Root 的版本、series、项目与类型；JSONB 限对象/非空/1 MiB，schema_version=1，SHA-256 长度为 32 字节；所有写操作闭锁。无 API、权限或依赖变化。
- Verification：Win11 可弃 PostgreSQL 18.6 空/有 Project 数据升级、空历史降级重升、复合 FK/类型/形状/大小/指纹/重复及非空拒降、DML/TRUNCATE 拒绝和 drift 退出 0；A02/A03 根及 refs 回归均退出 0；定向清单 7 通过、后端全量 3601 通过/3 跳过/5612 子例，开发 wheel 构建通过。首轮 Schema 脚本仅将实际主键约束名写错，修正后全脚本通过。
- Risk/rollback：仅空载荷表能降回 0162，非空保留历史；Root/refs/payload 写入口均未开放。四类业务语义、来源资格、OutputArtifact、授权 Owner、审计、Trace/Section 引用和 Review 待后续 WBS。Gate3/Pilot/正式发行未放行，Server2025 未实测，Debian13 实机按用户指令跳过。
