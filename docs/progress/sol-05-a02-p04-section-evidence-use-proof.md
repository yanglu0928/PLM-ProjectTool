# SOL-05-A02-P04：SectionVersion PROJECT Evidence 现时/物理证明最小投影

日期：2026-10-09。结果：`SECTION_EVIDENCE_USE_PROOF_INTERNAL_PASS`；仅内部适配器与上游服务复验，未创建 SectionVersion。

## 编码前检查

Phase 2 Platform Core；输入 Gate2 DM-05/API-04、CR-SOL-003/0138、SectionVersion 输入与 Document/Requirement 证明、Evidence 已有 `EvidenceFixedProjectSourceService`。前置满足。单一问题是确保章节固定 Evidence ID 同项目、现时 ELIGIBLE、底层 Document/Parse/Locator/文件指纹可用，而不是仅凭 FK/状态列。涉及 Solution→Evidence 内部 Application Port；不改 Evidence 服务、实体、Schema/Migration、API/权限。验收为 PM/实施成员、固定身份/锁版本/指纹最小投影，以及客户角色/跨项目/失效/异常失败关闭。风险为将 Evidence 可用误称业务覆盖或客户 Review 完成。

## 实施与证据

新增 `SectionEvidenceUseProof` DTO/Port 与适配器，调用 Evidence-owned 项目固定来源服务，输出仅 Evidence/Project/Document/Version ID、锁版本和32字节指纹；再次限定 PROJECT、同项目、ELIGIBLE、真实验证人及 PM/ImplementationMember。原文件名、Locator、正文、Parse 内容和客户角色信息不传给 Solution。未来装配必须将上游服务角色显式限制为 PM/ImplementationMember；即使误装过宽，适配器也拒绝客户角色。此端口尚未加入写 Owner。

定向 pytest `5 passed, 16 subtests passed`，覆盖同事务与最小投影、IM正例、输入/跨项目/状态/角色/指纹负例及上游异常；后端全量 `3512 passed, 3 skipped, 5455 subtests passed`、退出0。现有 `validation/evd-01-a03-p02-a02-p01/verify.py` 的 Win11隔离PG上游固定来源脚本复跑退出0；该脚本不调用本新适配器，不能算 SectionVersion PG端到端。本项未运行章节版本写入、浏览器或正式服务账户。

兼容/升级/回滚：仅新增未接线内部端口/测试，无 Schema/Migration、公开 API、权限、配置、依赖或数据变化；撤适配器即可回滚，0138闭锁保留。下一项 `SOL-05-A02-P05` 校验 Section 当前父目录/版本序列基底，再规划受控 Owner/Guard。正式Server2025/信任、20并发、AI质量、Gate3/发行仍未通过；Debian13实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003/0138 → SOL-05-A02-P01～P03 → DEC-1170 → 本证明 → SectionVersion Owner/Guard → VALIDATE/Review/Trace → Gate3。
