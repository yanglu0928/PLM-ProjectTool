# SOL-06-A09-P01：完整草案集合写入闭合

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：Gate 2 DM-05/SC-01 → DEC-1202 → 0161～0163 → 0164 → 本项。
- Changed：仅新增 0164 触发器迁移，打开 Root/Payload/Requirement/Section/Evidence 五类完整 DRAFT INSERT，严禁修改/删除/截断和提交后补写；series 串行升版、同 Project/Type 前驱、同事务引用集合及提交闭合。ArtifactRef 保持闭锁。ORM 未增减表列，仅 Root/Payload 注释更新；迁移 head 测试更新。无公开 API/权限变化。
- Verification：Win11 可弃 PG18.6 真实空/有数据升级、空表降级重升、完整/缺集合、顺序空洞、裸 Artifact、升版前驱、并发同 series、提交后补写、不可变和非空拒降/drift 脚本退出 0；旧 0161～0163 历史验证固定各自 revision 后全部复跑退出 0。首次定向测试发现离线 SQL 渲染被新 guard 拒绝，调整为仅在线升级检查已有历史后复跑定向 7 通过。后端全量 3621 通过/3 跳过/5677 子例，开发 wheel 与迁移入包检查通过。
- Risk/rollback：仅全空集合允许降回 0163；出现非空历史必须保留并升级修复。当前虽可由受控数据库事务写完整行，SOL-06 正式服务 Owner/Project 操作授权/持久幂等/Audit 尚未安装，故不能让普通用户创建专项，也不能把直接 SQL 合成行当成正式业务事实。OutputArtifact 缺失；Section VALIDATE、Review/Gate3/Pilot/正式发行未放行。
- Next：`SOL-06-A09-P02` 实现同事务 Repository/首结果重放，再接正式写 Service 与 Windows/HTTP/UI；每项独立验收。
