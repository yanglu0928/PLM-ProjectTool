# SOL-06-A10-P01：结构化专项历史详情内部读取

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：冻结 SOL_SPEC_GET → SOL-06 0161～0164 → A09 创建/浏览器验收 → 本项；决策见 `DEC-20261016-1204`。
- 编码前检查：Phase 2；前置创建、固定引用与项目权限机制已存在。涉及 Solution 内部 Service/Repository、SOL-06 固定历史及项目成员只读策略；无公开 API/Schema/新依赖。目标为创建后能安全读回草案，不把首次创建回执当现时历史。风险为跨项目泄漏、缺子表仍返回不完整正文及误报版本状态。
- Changed：新增按项目限定的内部详情读取，重建固定类型化 payload、Requirement/Section/Evidence 引用及当前版本/Review 字段。校验顺序、重复引用、payload 指纹、字段配对；缺失或损坏失败关闭。Session、有效 License 和项目成员授权在读取前执行；跨项目不可见。
- 验证：单元 3 项；Windows 11 可弃 PostgreSQL 18.6 真实合成来源/Session/项目授权下读回同系列 v1/v2，项目成员可读，跨项目及无效会话拒绝；后端全量 3633 通过、3 项既有跳过、5706 子例通过。开发 wheel 含两个新增模块（1395 个条目）构建通过。初次全量回归仅因策略矩阵旧总数断言失败，补入新读策略断言后复跑全绿；初次 wheel 命令在测试环境缺 pip、系统环境缺无隔离 setuptools，改用隔离构建成功。
- 兼容性/升级/回滚：无 Migration、公开 API、旧数据写入或依赖变化；内部读取/策略可撤，已有历史不动。合成 License/账户不等于正式信任。
- 限制：OutputArtifact Owner 尚未建立，当前历史含 Artifact 引用会失败关闭。HTTP GET、Windows 装配、前端详情、Review、章节六维可送审、Gate 3/Pilot/正式发行未完成。
- Next：`SOL-06-A10-P02` 冻结 `SOL_SPEC_GET` HTTP 详情投影与权限/异常合同。
