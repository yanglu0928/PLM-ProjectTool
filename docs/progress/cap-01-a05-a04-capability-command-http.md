# CAP-01-A05-A04：Capability 六个普通命令 HTTP

日期：2026-10-05。结论：`CAP_01_A05_A04_COMMAND_HTTP_PASS`。下一项：`CAP-01-A05-A05` Capability Version送审外层。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A04
输入基线：冻结API-01/API-04、DM-05、Schema0095、DEC-840～842
前置任务：Baseline/Version Create、Validate、Patch/Archive/Restrict内部Owner均通过
涉及模块：capability api/application/infrastructure；platform create_app
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem、Document/Evidence固定引用
涉及API：六个冻结普通命令；不含submit-review和五个GET
涉及权限：可信Origin、Session/CSRF、DeploymentAdmin、License；Owner内再次复核
验收标准：六路合同、强ETag/幂等/严格JSON、安全错误、默认404、wheel可执行
风险：PATCH伪全量覆盖、半成品生产挂载、默认FastAPI校验泄漏、路径UUID/引用绕过
```

## 实施结果

- 新增统一 opt-in Router，接通 Baseline Create/Patch/Archive、Version Create/Validate/Restrict；`create_app` 仅增加可选注入点，默认不装配并保持404。
- 所有请求先完成 Origin、Cookie Session、CSRF、query/body/header边界；业务Owner继续执行DeploymentAdmin、License、资源状态、持久幂等及Audit的事务内复核。
- Baseline PATCH按冻结API-01落实非空受控partial DTO：name和description可独立更新，显式null只允许清空description；Repository在行锁后合并，no-op失败关闭。
- Version输入使用完整CapabilityItem快照，固定Document/Evidence引用；输出只含安全投影。补登记冻结API-04既有`CAPABILITY_EVIDENCE_REQUIRED`错误码。
- 未接入`production_login.py`，因此当前只在显式测试/调用者注入时存在；Windows生产组合留在A05-A07。

## 验证与证据

- 合同与Owner定向21项通过；覆盖六路201/200、默认六路404、Origin/Session/CSRF、幂等键、强ETag、partial PATCH、重复键、未知/空字段、query和canonical UUID拒绝及安全错误映射。
- Win11/PostgreSQL 18.6真实A03链复验通过；partial name更新保留description，后续Review栅栏、限制、归档、Audit和拒降均通过。
- 后端全量2583项通过、3项按既定环境条件跳过；`compileall`与`git diff --check`通过。
- 最终开发wheel内Capability HTTP/Owner 47项通过；解包wheel后Migration 4项通过。wheel SHA-256 `21eab4dfe4ba29762e180606ba377bd685328a90cda48f02894eaf4d8c8650eb`。

## 兼容、回滚与未关闭项

无Schema/Migration/依赖/配置/网络/Secret/外发变化。公开URL和Operation保持冻结V1；partial PATCH是API-01既定语义落实。停止注入Router即可回滚新HTTP流量，已提交的合法业务历史保留。

送审外层、五个读取Router、Windows真实HTTP组合、前端、正式信任/性能/Gate3/发行仍未关闭；本项不宣称生产可用。
