# PLT-PKG-01-A09-P51-A28：受限 Windows 启动协调器前置守门验收

- 日期：2026-10-30
- 结果：PASS_LIMITED
- Hosted workflow：Windows Server 2025 run [40981581644](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40981581644)，head `3b806c5709dadace9ace57ab793b1f0dc4f0d717`；10/10 jobs success。
- 执行位置：GitHub hosted Windows runner 的 D: RUNNER_TEMP；未在用户本机运行代码。

## 证据

- 包内启动前置合同定向单测：2/2通过。manifest 显式列出正式产品公钥、License 信任、数据库凭据目标引用、服务身份 ACL、TLS 证书和私钥的状态。
- 同源父包候选：20,118个payload文件；ZIP SHA-256 `94836090772c99dca116e105b80de6379ca07481c126098fb36c05764db80e8b`。manifest保持`release_eligible=false`和`legal_clearance=false`。
- 实际父包PG smoke读取manifest并逐项核对摘要：公钥、正式License信任、数据库凭据引用验证、服务ACL、TLS证书/私钥均为false；明确目标引用为`PLMProjectTool/Database`，阻断码与manifest一致。
- 包内启动器运行结果为`FAIL_CLOSED_MISSING_FORMAL_PRODUCT_TRUST`；生产入口探测为`FAIL_CLOSED_MISSING_ACCOUNT_DATABASE_CREDENTIAL`。stdout为空，输出为固定拒绝信息；绑定回探测端口成功，说明该产品入口未留下监听端口。
- PG smoke使用本轮隔离目录和临时数据库，PG 18.6/pgvector 0.8.6生命周期通过；loopback Caddy静态资源/API代理 smoke通过（HTTP，不声称TLS验收）。生产API未启动，临时数据库已停止并清理。
- 同轮A17包内PlanVersion Edge/HTTPS/PostgreSQL验收成功：20,112项候选；Create/Get/Validate/SubmitReview/Review读回共29次API调用；DB状态为PlanVersion `IN_REVIEW`，WBS/Requirement/Validation数量为(2,2,1)，Review/Round为`IN_REVIEW/IN_REVIEW`，客户决定数0。候选SHA-256 `5b346894d8fa925100e0897b66c49791a519f796a91801b240a125c7a69d7aed`。测试身份为合成身份。

## 限制与结论

此结果证明当前非发行包在明确缺少正式信任材料时失败关闭，不证明正向生产启动可用。正式产品公钥、真实License信任、数据库凭据供给、服务身份/ACL、正式TLS部署、Windows 11设备安装/升级、用户验收和法律放行仍未完成。Pilot、Gate 3及正式Release继续NOT_READY；不从Windows Server 2025 hosted结果推定Windows 11设备或Windows Server 2025产品安装兼容性。

## 追溯

- 编码前检查及首轮validator偏差：`docs/progress/plt-pkg-01-a09-p51-a28-startup-coordinator-precheck.md`
- 父包候选 artifact 12945427342；包内A17候选 artifact 12945582160；A17证据 artifact 12945353590；PG smoke证据 artifact 12945037587。Artifacts保留至2026-11-13左右。
- 源代码候选分支：`feature/p51-embedded-runtime-cache`。
