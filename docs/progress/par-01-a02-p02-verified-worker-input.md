# PAR-01-A02-P02 当前租约下的受控 Parser 输入快照

- 日期/结果：2026-09-30；Phase 2 依赖前置；`WINDOWS11_SYNTHETIC_JOB_FILE_PG_PASS`（仅输入准备）。编码前检查：`CR-PAR-001`、A01 profile、A02-P01 Document 内部来源元数据、既有 Job Lease/Outbox 和 LocalFileStorage 私有快照已具备；决策 `DEC-20260930-499`。
- Changed/Files：新增 `modules/parser/application/prepare_input.py` 与定向测试；扩展已隔离的 `validation/doc-03-a04-a04-upload-finalize-platform/verify.py`。当前 Job fencing token/worker、DOCUMENT_PARSE Job/Outbox 和 Document 上传/Audit/固定版本在第一短事务验证；事务外复用受控存储复制并核 SHA-256/长度；第二短事务重核完全相同来源与租约。只返回已验证私有字节流/profile，不返回物理 locator。文件完整性故障失败关闭并以 SystemActor+原用户引用写无路径 Audit。
- Tests：定向 6 项 PASS，含错误/过期租约、队列或来源漂移、篡改和 Audit 失败拒绝、快照关闭；Python3.13 后端全量 1578 项 PASS（2 项既有跳过）。Windows11 临时 PostgreSQL18.6/实际合成 PDF 上传 Commit 后手动领取 Job：当前租约读回原字节/Profile，错误 fencing 在开文件前拒绝；篡改该临时文件后 Hash/大小拒绝并留下精确一条 `DOCUMENT_PARSE_INTEGRITY_FAILED` Audit，夹具 exit0，随机库/文件根清理。隔离 wheel 构建及模块包含 PASS；PoC PG 恢复停止。
- 兼容/升级/回滚：不改 ORM/Migration、公开 `/api/v1`、权限、依赖或技术栈，兼容 DB0049；无升级动作。撤独立 Parser 输入服务/测试接线即可回滚，既有上传或 DocumentVersion 不变。真实文件篡改只发生在自建隔离临时根，并随夹具清理。
- Known Issues/Next：实际独立 Worker loop、心跳、解析/OCR、结构化结果、ParseRecord 原子发布、取消/重试和 Evidence 精确定位未实现；本项不能冒称这些能力。后续 `PAR-01-A03` 从已验证快照执行按格式的真实解析并保留可复验源位置，随后单独处理发布与 Worker 装配。正式信任、Server2025/Debian、性能/Gate3/可用包仍待。
