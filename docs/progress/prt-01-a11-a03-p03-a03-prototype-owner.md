# PRT-01-A11-A03-P03-A03：Prototype Workflow 真实聚合资格 Owner

日期：2026-10-08。状态：内部 Owner/端口合同验证通过；未注册 Workflow、未做 PostgreSQL/HTTP 组合，不是正式 Gate PASS。

编码前检查：Phase 2/Gate 2 冻结架构、`CR-PRT-005`、A11-A02 纯范围策略及 A11-A03-P01/P02/P03-A01/A02 已核对。本项只实现 Prototype 资格 Owner 所需的 Audit/Document 公开证明端口与应用层聚合，不改 Schema、冻结 `/api/v1`、权限或既有写操作。输入为受权 Workflow 调用者同一事务：完整 Requirement Scope 与 Requirement 正式资格、稳定验收标准引用、Prototype 根/决定/Version/Link 锁定输入、Review、Audit、Document 本体。验收是全量二分范围与覆盖失败关闭，不能由候选/元数据冒充正式事实。风险是物理文件读取开销和旧决定 Audit 关联为项目/根/用户/近邻时间证明而非独立外键；A05 需真实 PG/文件/性能验证。回滚为不注册本 Owner，历史不变。

实现：`PrototypeWorkflowQualificationOwner` 先持有项目范围锁，再把 Requirement Owner 的正式 `REQUIREMENT_ACCEPTANCE` 聚合与完整批准快照逐条对账；NOT_REQUIRED 每条核对固定需求版本、确认人、Audit 成功动作，可选已批准 Review；需原型分支重证当前 Template/Requirement/Document 元数据与版本内容指纹、逐文件物理 SHA-256/长度/文件身份、批准 Review/Trace 清单、ACTIVE Link 精确覆盖。`PROTOTYPE_SCOPE_DECISIONS` 检查完整二分；`PROTOTYPE_COVERAGE` 额外检查全部验收标准已由有效 Link 覆盖。混合主体按各自 Review 和 Evidence 归属写入聚合指纹；任何缺证明统一 `WORKFLOW_GATE_NOT_SATISFIED`。无客户数据外发。

Document 所有者公开接口返回无路径的物理校验证明，数据库状态与版本/FileObject 元数据须一致，使用既有安全存储验证实际字节、哈希、大小和文件身份。Audit 所有者公开接口只证明 PM 的受权动作见证，不称为客户签署；限定项目、原型、用户、动作和唯一近邻事件。`CR-PRT-005` 已在代码实施前补记“仅元数据不足”偏差、磁盘开销和回滚计划。

验证：Owner 定向覆盖全 NOT_REQUIRED、缺 Audit/验收引用/跨项目、需原型完整覆盖、缺物理证明/Link；Audit 端口 2、Document 端口 3、既有范围端口回归通过；后端全量 3237 通过、3 条件跳过、4791 子例通过。真实 PostgreSQL 行锁/文件哈希/HTTP/浏览器与性能尚未执行，不将内部合成测试扩大为实机结论。下一步 A11-A04 注册与预览/Checklist/阶段推进，A11-A05 真实 Win11/PG/HTTP 验证；Server2025 另行验证，Debian13依用户指令跳过。

TraceLink：`CR-PRT-005` → `DEC-20261008-1073/1074/1075` → A11-A03-P01/P02/P03 → A11-A04 → A11-A05 → Gate 3。
