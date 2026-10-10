# SOL-01-A04-P09-P01：GLOBAL Reference 读取与创建后定位前置核查

日期：2026-10-09。结果：`GLOBAL_REFERENCE_READ_PRECHECK_PASS`，仅冻结合同/现有 Owner 差距对账，不代表 GET/List 已实现。

编码前检查：Gate 2 冻结 API-04 把 `SOL_REFERENCE_GET`/`SOL_REFERENCE_LIST` 分别展开为 PROJECT 和 GLOBAL 路径；P06-P05-P04 已实测 GLOBAL Create201 与 `Location:/api/v1/global/reference-solutions/{id}`，但目前该 GLOBAL GET/List 未挂载，客户端无法随后打开已创建对象。现有 `ReferenceReadService`、DTO、Repository、游标和 HTTP 均明确只认 PROJECT/非空 ProjectId，不能将 GLOBAL 直接传入 PROJECT 实现，也不能把 `Location` 的 201 当 GET 已通过。

角色/范围：GLOBAL 路径首版仅当前 DeploymentAdmin 通过有效 Session/License 读取，不通过客户端传入 ProjectId 伪装项目成员资格。PROJECT 成员使用 PROJECT 路径，未来如需项目内引用 GLOBAL，则由对应项目 Owner 在其受权业务路径明确证明；本任务不增跨项目全局浏览权限。GLOBAL GET 返回当前版本和固定来源身份，不返回客户正文、Secret 或脱敏确认声明为当前有效；Source 物理内容需逐条经过现有受权 Document/Evidence 入口。GLOBAL List 仅安全摘要、有界分页与专用签名游标，Project 游标不能重用。

实施顺序：P09-P02 独立 GLOBAL 只读 Owner/Repository 与隔离 PG 身份/Scope 负例；P09-P03 GET HTTP、Windows 只读组合及实际 PG；P09-P04 List 游标/HTTP/Windows/PG；P09-P05 前端候选/详情导航与 Edge。先确保 GET Location 可兑现，再做 List。每项保留原冻结字段/PROJECT 行为与默认关闭策略，必要的细化投影须记录 API 增量合同；若出现 Breaking Change，先 Change Request 并独立版本化。

创建超时恢复：现有 Confirm/Revoke 原 Key 回查不能查询 Create 收据；GLOBAL GET/List 完成后可改善人工核对，但不能仅以名称推断原 Key 的首次结果。若需要安全的原 Key 精确查询，须先单独登记 Change Request、明确 Actor/Operation/Key 隔离、当前授权和首次不可变结果及迁移/回滚，再实施；当前 UI 保持不确定锁定，不自动重复写入。

兼容/风险/回滚/验证：本项仅文档，无代码/Schema/依赖/数据迁移；不能将 Admin-only 设计扩成任意项目成员全局读取。生产正式 License/账户、真人资料确认、Server 2025、20 并发、Gate 3/UAT/发行独立未验，Debian 13 依用户指令跳过。TraceLink：冻结 API-04 → P04 PROJECT GET/List → P06 GLOBAL Create → 本 P09-P01 → P09-P02～P05。
