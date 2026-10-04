# HND-01-A04-A02-P04：Handover Review Windows写组合与真实HTTP/PG

日期：2026-10-05。结论：`HND_01_A04_A02_P04_WINDOWS_HTTP_PASS`。下一项：`HND-01-A05-A01` Analysis剩余HTTP Operation与读取Owner前置。

## 实施结果

- 新增单一Windows Handover Review composition，在共享runtime/UOW中组装Session访问、Project授权、Reviewer资格、License、Audit、收据、Review三仓储和真实`HND-02` Subject Owner。
- 只在`create_production_platform_write_app`/`--platform-write`注入四个Review写路径；默认app、login-only及只读Platform不调用写组合工厂。
- 未增加Secret、配置、依赖或新Owner白名单；不将Capability GLOBAL Review或未知Subject接入本PROJECT Router。

## 客观验收

- Windows 11/PostgreSQL 18.6全新临时库、Schema head/drift下，从Windows composition创建ASGI app，以真实Session/CSRF/Project成员和Handover业务事实完成create/start/approve、批准后升版、create/start/withdraw。
- 四个HTTP命令的原幂等键重放均返回首次不可变`data`；最终V1为APPROVED/CONFIRMED且保持正式指针，V2为RETURNED/CANDIDATE。临时数据库已删除。
- 原P02内部链在向后兼容扩展后独立重跑PASS；Windows composition/生产组合定向34项、后端全量2674项通过、3项条件跳过。
- wheel构建并直接导入Windows Review composition通过，SHA-256 `4b3419d4679ad44b0d95a2d79621859238da928257942c6699e327cb2f7e03f9`。

## 兼容、回滚与剩余边界

无Migration、冻结API破坏、依赖、Secret、网络或数据外发。停止注入`review_command_router`即关闭新HTTP写入，已有Review/Handover历史保留。本项是Windows 11证据；Windows Server 2025/Debian 13、Review读取及前端、Analysis/Action剩余HTTP、Gate 3与发行仍未因此通过。
