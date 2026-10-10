# SOL-05-A03-P02：SectionVersion 历史 GET/LIST 内部 Owner

日期：2026-10-10。结果：`SECTION_VERSION_READ_OWNER_PG_PASS`；仅内部 Application/Repository，不开放 HTTP 或 UI。

## 前置与范围

当前 Phase 2、WBS `SOL-05-A03-P02`；输入 Gate2 冻结 API-04 的项目成员 GET/LIST 与固定 content/Requirement/Evidence 引用、CR-SOL-003、0160 SectionVersion 创建闭环、A03-P01 已验权限。涉及 Solution 内部只读 Owner/SQL Repository；无 Schema、Migration、公开 API、角色矩阵或依赖变化。验收为现时 License/Session/项目成员重验、同项目 Section/Version 身份、固定引用顺序/计数、原首响应不可变字段一致、历史状态安全投影、倒序有界分页、异常失败关闭。风险是把旧固定来源当成现时资格、用 CREATE 首响应替代当前 Review 状态、或缺损历史泄漏。

## 实施与验证

按 DEC-1182 新增 `SectionVersionReadService` 与 `SqlAlchemySectionVersionReadRepository`。每次 GET/LIST 在同一事务中验证 License、真实 Session、当前 Project 成员操作授权，读取 Section 逻辑身份和批准指针一致性；版本按 ProjectId/SectionId 隔离。Repository 读取版本根、不可变首次结果和有序 Requirement/Evidence 固定引用；声明数、ordinal、重复身份、根/首响应不可变字段不一致均失败关闭。返回历史正文引用 ID、指纹、声明、Review 元数据，不返回物理路径/来源正文，也不重证现时文件/资格。LIST 每页最多100，按版本号倒序；公开 HMAC 游标和 HTTP 留后续独立任务。

定向单元 3 通过/9 子测试：四类当前项目成员、分页、会话/项目/License/根/坏版本/乱序失败关闭。Windows 11 可弃 PG18.6 验证脚本 `validation/sol-05-a03-p02-section-version-read-owner/verify.py` 退出0，复用 P11 的五个真实提交版本，经理与实施成员 GET、三页 LIST、跨项目/错误 Section/匿名/License 拒绝、来源文件变化不改历史、合成破坏首响应时拒读并恢复、读链不增加版本/Audit；上游来源/CREATE 夹具同次通过。Requirement APPROVED 来源是合成一致夹具，不是客户确认。后端全量 3540 通过、3 跳过、5558 子测试通过。

兼容/回滚：无旧数据、Migration、公开 API/权限变化；可撤未装配的内部读取代码，历史版本不删。旧0138完整迁移脚本仍未恢复 PASS，正式 HTTPS/目标账户/公钥、Server2025、性能、Gate3/Pilot/发行未通过；Debian13实机按用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → P12 CREATE → A03-P01 授权 → DEC-1182 → 本 P02 → 后续 HTTP/Windows/UI → Gate3/Pilot。
