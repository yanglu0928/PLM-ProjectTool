# SOL-05-A02-P11：SectionVersion 受权 CREATE Owner

日期：2026-10-09。结果：`SECTION_VERSION_CREATE_OWNER_PG_PASS`；内部业务 Owner/持久收据与真实来源组合通过，非公开 HTTP 或正式环境 PASS。

## 编码前检查

Phase 2 Platform Core；WBS `SOL-05-A02-P11`。输入 Gate2 DM-05/API-04、CR-SOL-003、P01～P10；前置授权策略、来源证明、0160 原子闭环满足。单一问题是在 Solution 内部以同一事务创建 DRAFT SectionVersion、固定引用、首次响应、持久幂等收据及 Audit。无新 Schema/Migration、公开 API 或权限规则。验收为真实 Session/CSRF、License、当前 ProjectManager/ImplementationMember 权限、Document/Requirement/Evidence 现时证明、首响应重放、同/异 Key 并发、来源失效与失败整事务回滚。风险为重放绕过现时授权、Artifact 裸引用进入持久层、部分提交或重复审计。

## 实施与证据

新增 `SectionVersionCreateService` 与 `SqlAlchemySectionVersionCreateRepository`。Owner 先校验有界输入与幂等 Key、当前 License/Session/CSRF/Project 角色，再在同事务预留收据。已有完成收据只从不可变首次结果与固定引用表重放，且每次仍重验当前授权；新请求经 P06 的当前 Section 基底、Document 物理字节、已批准 RequirementVersion、Evidence 当前资格组合证明后，插入 DRAFT 版本和引用、首响应、Audit，完成收据并提交。失败由 UoW 回滚。Artifact 分支继续拒写；AI 建议不成为正式批准事实。

Windows 11 一次性 PG18.6 合成组合脚本 `validation/sol-05-a02-p11-section-version-create-owner/verify.py` 退出0：真实 Auth/Project/Document/Requirement/Evidence 适配器、非空固定 Requirement/Evidence 引用、经理/实施成员首次创建与连续升版、同键重放/不同请求冲突、同键只一次及异键连续并发、撤权/错项目/License 拒绝、Evidence 变 INELIGIBLE、Requirement 批准指针失效、Document 字节篡改时新建拒绝而原键重放、Artifact 拒绝及 Audit 失败零持久化。PG 中 Requirement/Review 是一次性合成、结构一致的 APPROVED 夹具，不代表真实客户确认；Document/Evidence 私有文件与读取链由真实服务验证。先前测试把 Evidence 改为不可逆 REVOKED 后无法恢复，已改用可恢复 INELIGIBLE；生产规则未改。定向单元 6 通过/4 子测试；后端全量 3532 通过、3 跳过、5514 子测试通过。

兼容/回滚：无 Migration、冻结 API、权限、依赖、配置或既有数据变化；内部 Owner 尚未挂 HTTP/Windows 路由，移除新内部服务/仓储可回滚，已创建的历史、首次结果、收据与 Audit 不可删。P12 需单独验证 HTTP/Windows 显式装配、错误合同及真实浏览器；Review/Trace/Spec/Artifact 后续独立验收。正式 Server2025/信任源、20 并发性能、质量、Gate3/发行未通过，Debian13 实机依用户指令跳过。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-003 → P08～P10 → DEC-1177 → 内部 CREATE Owner → P12 HTTP/Windows → Gate3。
