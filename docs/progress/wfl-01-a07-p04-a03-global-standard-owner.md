# WFL-01-A07-P04-A03：窄 GLOBAL 标准来源内部 Owner

日期：2026-10-02；Phase 2；原冻结基线提交 `64cdf09` 不改，偏差 `CR-WFL-005`、决策 `DEC-20261002-606`。状态：**内部 Port PASS；Workflow 写链未装配**。

Document 独立内部 Port 用当前 Session 与目标 ACTIVE 项目的 PROJECT_MANAGER 权限，仅锁定 GLOBAL `STANDARD_CAPABILITY` 的 Document/Version/File 与可选 ParseRecord/ResultRef，并读取实际私有文件/解析结果做 SHA、固定版本及 Parser JSON 校验。Evidence 内部 Owner 锁定当前 GLOBAL ELIGIBLE 行，对固定 locator/node/fingerprint 与 Document 结果复验，只返回目标 ProjectId、来源身份和最小观测事实；不返回正文或存储路径，也不授予项目经理普通 GLOBAL 列表/详情/下载。

验证：新增单元 6/6（会话失效、License 拒绝、角色/归档、非标准类别、整文档、解析节点及篡改）；隔离 PostgreSQL 18 合成 GLOBAL 整文档和固定节点通过，Evidence/Document/Version/File/ParseRecord/ResultRef 六行共享锁下第二连接 `FOR UPDATE NOWAIT` 均为 `55P03`。普通 GLOBAL 详情对 PM 仍返回拒绝；跨项目、Evidence 撤销、实际文件与解析结果篡改失败关闭。后端全量 1852 通过/3 跳过；开发 wheel SHA-256 `f314ba6aab0e368481c66ba2828b9a481e14b4489be43634a2adbf78bff3c27d`。

兼容/升级/回滚：无公开 API、Schema/Migration、依赖、旧行回填或生产数据修改；可不装配下游并保留 Checklist/Gate 写关闭。隔离 PG18 的 Session/项目角色是受检假 Port，实际 Workflow+Session/CSRF/License/Audit/收据、真实 Review/ApprovedException Owner、正式信任/法律、Server2025/Debian/UAT/Gate 均未因本任务通过。该 Port 不能被当作通用 GLOBAL 下载入口。
