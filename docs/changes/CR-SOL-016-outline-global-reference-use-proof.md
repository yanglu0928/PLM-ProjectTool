# CR-SOL-016：OutlineVersion 使用 GLOBAL 参考方案的现时证明边界

日期：2026-10-09。状态：实施前登记；按 `CR-EXEC-001` 持续授权执行，Gate2 冻结基线 `64cdf09` 不回写。来源：`SOL-03-A04` 编码前检查、冻结 API-04/DM-05、`CR-SOL-002`、`SOL-01-A16`。

## 冲突与证据

冻结 `SOL_OUTLINE_VERSION_CREATE` 允许 ProjectManager 或 ImplementationMember 固定当前 `ELIGIBLE` 的 PROJECT/GLOBAL ReferenceVersion。当前 `ReferenceSourceQualificationService.qualify()` 的 GLOBAL 路径依赖 `ReferenceDeidentificationProofService.prove()`，后者通过当前调用者 Session 再次要求全局管理员；GLOBAL Evidence/Document 原始读取也走调用者读授权。把此路径原样注入目录 Owner，会错误拒绝合法项目角色；给项目角色全局管理员权限或透传管理员 Session 则扩大权限并泄漏全局来源。仅检查历史 `ELIGIBLE` 事件或 0154 FK 则不能证明当前来源与脱敏确认仍有效。

## 方案比较与选择

- 不选要求每次目录创建由全局管理员代办：破坏冻结角色合同与项目审计归属。
- 不选跳过 Document/Evidence/确认现时性或复用旧资格事件：会在撤回、文件不可用、确认过期后仍接受来源。
- 选择建立只供受权业务 Owner 调用的服务端、只读、最小投影 `CurrentEligibleReferenceUseProof`：输入固定 Root/Version/Scope/目标 Project 和调用者已获授权的业务上下文；Solution 内同事务锁定当前 Root/Version 与资格事件，复核 `ELIGIBLE`、版本当前性、Scope/Project、固定来源集合闭合；经 Document/Evidence 自有 Application Interface 取得当前可用性/摘要证明，GLOBAL 另验证原管理员人工脱敏确认仍未撤回/过期且与固定来源指纹一致。只返回通过与固定标识/摘要，不返回正文、存储定位、全局管理员凭据或原始来源列表给项目 UI。不得把该接口暴露为任意项目用户的 GLOBAL 文档浏览入口。

## 差异、影响与安全边界

这是冻结合同的实现边界细化，不改变 `/api/v1` 路径、请求字段、角色或产品 Scope。需增 Solution 的内部证明 Port/Service，并在必要时新增 Document/Evidence 自有的受限服务端可用性 Port；跨模块只通过 Application Interface，禁止 Solution 直接读上游内部表。PROJECT 路径继续执行同项目现时来源证明；GLOBAL 路径不以项目用户身份阅读全文，只在已合格 Reference 的固定版本上执行内部可用性核查。证明不能被直接客户端请求，也不能代替 201 DRAFT 创建时的独立权限、计数、幂等和审计。

## 迁移、回滚与验证计划

本 CR 第一阶段只登记设计，不执行数据库迁移或开放写。后续若需要 Schema/Guard 变更，必须单独线性 Alembic 迁移、空/有数据 up/down、历史拒降并保留 0137/0154。服务级回滚为保持 OutlineVersion 写 Guard 关闭、撤掉内部证明接线；不得撤销既有 Reference 资格历史。验证至少覆盖：合法项目成员引用 GLOBAL 合格版本、项目成员不能浏览 GLOBAL 原文/调用管理员资格命令、跨项目 PROJECT 拒绝、旧版本/RESTRICTED/REVOKED/缺事件拒绝、Document/Evidence 不可用/摘要变化、GLOBAL 确认撤回或到期、并发资格变更、失败无目录版本/Audit/收据、SQL 约束和全量回归。测试须使用合成数据，不发送客户正文或 Secret 外部服务。

在现时证明 Port 完成前，`SOL_OUTLINE_VERSION_CREATE` 保持关闭；Gate3 不据此通过。TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/0154 → 本 CR → A04 内部证明 → A04 Owner/Guard → Gate3。

## A04-P01 实施记录

2026-10-09 已新增只含固定身份/摘要的内部 Query、Current snapshot、来源/确认 Port 与失败关闭校验服务；无账号提权、文档正文/定位输出、公开 API 或数据库更改。Mock Port 定向测试覆盖合法 PROJECT/GLOBAL 和旧版本、资格事件不一致、摘要变化、确认撤回/过期等拒绝。真实端口未接线，因此仅标合同 PASS，未将 Mock 结果宣称为当前来源可用；P02 仍需真实 PostgreSQL/文件/权限验证。
