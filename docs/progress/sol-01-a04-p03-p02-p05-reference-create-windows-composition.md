# SOL-01-A04-P03-P02-P05：Windows 显式 PROJECT Reference 创建组合

日期：2026-10-09；结果：`WINDOWS_PROJECT_REFERENCE_CREATE_COMPOSITION_SYNTHETIC_PASS`。正式发行 License/目标服务账户未验，非生产 PASS。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P03-P02-P05
输入基线：Gate 2 冻结 API-04、CR-SOL-007、0144、P03-P02-P03/P04
前置：可选 HTTP 合同及隔离 ASGI/PG/文件通过
涉及模块/实体：Windows 组合根与 Solution 来源端口；无 Schema 变化
API/权限：仅显式 --platform-write PROJECT POST；GLOBAL/默认/只读模式仍关闭
验收：真实来源端口组合、缺依赖失败关闭、模式路由隔离、PG回归、全量后端回归
风险：正式公钥/服务账户Vault/ACL/HTTPS与安装恢复未验；GET/List/UI待
```

新增 Windows Solution 独立组合函数：复用既有受权 DocumentRead/Download/ParseResult 与平台许可守卫，组合当前 DocumentVersion 文件证明、PROJECT/GLOBAL Evidence 证明及 GLOBAL 脱敏确认 Proof；PROJECT Evidence 显式允许 PM/IM，符合冻结 API-04 和项目操作策略。`production_login` 仅在显式写模式注入 Router，默认/只读不挂载；GLOBAL 创建仍不开放。无新依赖、Schema 或 Breaking API。

隔离 PG18.6/私有文件的 ASGI 脚本改用该组合函数复验，PM 与 IM 均以 Document+Evidence 创建，重放、异载荷、跨项目、撤权、CSRF、文件篡改与许可拒绝均通过；原 GLOBAL/PROJECT 来源回归和 drift 同库通过。Windows 生产组合合同验证默认/只读路由404、写路由存在但未认证请求403、GLOBAL 404；单元验证每个依赖缺失均启动拒绝。全量后端 `3306 passed, 3 skipped, 4847 subtests passed`。

此次正式组合根测试仍使用合成 License/账户材料，不证明正式发行公钥、目标服务账户密钥、HTTPS/CA、Server 2025 或真实用户人工脱敏确认。Reference GET/List、后续版本/Eligibility/Review/Trace/Workflow、UI、20并发、Gate3/Release 未通过。TraceLink：API-04/CR-SOL-007 → DEC-20261009-1113 → Windows Solution 组合根 → 隔离 PG/生产模式合同/全量回归。
