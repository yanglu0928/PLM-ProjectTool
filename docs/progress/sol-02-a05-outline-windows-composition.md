# SOL-02-A05：Windows 显式目录创建组合

日期：2026-10-09；结果：`OUTLINE_WINDOWS_COMPOSITION_PASS`，限定 Windows 11 一次性 PostgreSQL 18.6、合成 License 与当前测试账户，不是正式发行信任验收。

```text
当前 Phase：Phase 2；依 CR-SEQ-001 前置 Solution 真实 Owner
当前 WBS：SOL-02-A05
输入基线：冻结 API-04、CR-SOL-011、A03/0146、A04 可选 HTTP
前置任务：A04 合同与真实 Session/ASGI/PG 已通过
涉及模块：Windows Solution 组合根及生产模式路由装配
涉及实体：SolutionOutline、首次结果、Audit/Receipt；无新 Schema
涉及 API：仅在显式 Windows 写模式装配 SOL_OUTLINE_CREATE
涉及权限：现有 Session/Origin/License/Project PM 或实施成员；缺依赖拒启动
验收标准：写模式受保护 POST、登录/只读模式 404、缺信任源失败关闭、PG 回归
风险：合成信任材料误报生产可用、创建后的 Location 尚无详情 GET
```

Changed：新增 Windows 专用 `create_windows_outline_create_router`，只从真实 Runtime、Session、Origin、License Guard、Audit 组合现有受权 Owner/Repository/Receipt。`production_login.py` 仅在 `include_secret_write` 显式写模式挂载；入口默认/只读模式不注入。缺任一必要端口抛统一启动错误，不泄漏原始异常；生产组合任一装配异常仍由上层关闭并释放 Runtime。API/Schema/依赖：无新变更；保留 A04 合同与 0146。

Tests：Windows 组合定向 1/5 缺依赖子例、生产模式合同合计35通过/7子例；Win11隔离 PG18.6 真实 Session/ASGI 经 Windows 组合的 201/重放/角色/跨项目/CSRF/License/默认404，以及 A04 原路由回归，均退出0。后端全量 `3365 passed, 3 skipped, 5021 subtests passed`。未使用正式公钥/目标服务账户，未在 Server2025 实机或真实浏览器测试；20 并发、Gate3/UAT/发行仍开放，Debian13 当前实机按用户指令暂跳过。

兼容/升级/回滚：无 Breaking API、Migration 或数据转移；关闭显式目录路由可恢复404，但已创建目录、Audit 和 Receipt 保留，不能删除。Location 指向的详情 GET 尚未实施，后续按冻结 SOL_OUTLINE_GET 与 LIST 单独验收。TraceLink：API-04 → CR-SOL-011 → A03/A04 → 本 A05 → SOL-02-A06。
