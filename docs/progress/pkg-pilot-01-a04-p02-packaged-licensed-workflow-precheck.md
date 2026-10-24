# PKG-PILOT-01-A04-P02：当前候选合成授权 Workflow HTTPS 前置检查

日期：2026-10-24；状态：`SYNTHETIC_PACKAGED_LICENSED_WORKFLOW_HTTPS_PASS / PILOT_NOT_READY`。

|检查项|结果|
|---|---|
|当前 Phase / WBS|Phase 2 / `PKG-PILOT-01-A04-P02`：固定候选在一次性合成有效 License 下经包内 Caddy/PG/API 验证 Workflow 入口|
|输入基线|Gate 2、CR-EXEC-002、CR-PKG-008～010；A02/A03/A04-P01 固定 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d`|
|前置任务|A03 无 License HTTPS 拒绝和 A04-P01 随包 Evidence 资格矩阵已通过；现有 WFL-01-A08-P07 验证脚本可复用显式候选 SHA 的合成授权/Workflow GET/START证明|
|涉及模块/实体/API|只运行既有包内合成验证，不修改产品；一次性 License/Project/Workflow 数据；冻结 `/api/v1/projects/{id}/workflow` 读与 START|
|涉及权限|合成 ProjectManager、CSRF/Idempotency、License有效性；合成签名私钥仅内存，公钥仅临时副本，不能当正式发行信任|
|验收标准|包内PG/API/Caddy启动，Workflow GET v0、START v1、同Key重放、错CSRF/异Key拒绝与单Audit/收据；候选同Hash，临时Vault/进程/布局清理|
|风险|现有脚本的业务断言可能与当前0185后的组合不一致；失败时如实记录并检查清理，不降低授权或冻结API规则|

本项只是一个包内授权业务切片，不代表项目→方案→计划完整纵向链、真实浏览器或正式 Pilot。

## 实测结果

从固定 ZIP SHA `527b1d91195b0594d513dbe4f95604ca53df7c11154b4299deff4880d27e4f5d` 的已验暂存构建两份各22,194件的隔离布局并逐件哈希读回。仅在测试内存生成 Ed25519 私钥，合成公钥写入临时副本，合成有效 License 写入一次性 PG18；不写原候选或正式信任源。包内 PG、Python API 与 Caddy 经 HTTPS 启动，错误 Host/Origin/未装 License 拒绝和登录/会话仍通过。

有效合成 License 后，项目经理经 HTTPS GET Workflow 得 v0/`NOT_STARTED`，首次 START 得 v1/`HANDOVER`/`ACTIVE`；同 Idempotency-Key 重放200且数据不变，缺 CSRF 为403，异 Key 在已启动状态为409；数据库回查恰有一个`WORKFLOW_STARTED` Audit和一个`V1_WORKFLOW_START`持久收据，无多余 StageTransition。业务验证器输出固定 PASS 标记，整体脚本退出0。候选 SHA 前后不变，48个合成 Vault 引用、临时数据库/API/Caddy与两份布局完成后清理；独立再查固定目标占用0。

Changed/Files：本项仅新增验收记录及版本/状态说明，复用已存在的 `validation/wfl-01-a08-p07-packaged-https/verify.py` 与 A03 已验证的烟测适配器，无新产品代码。Migration/API/权限：无变更。Tests：固定候选真实隔离 HTTPS/PG/License/Workflow 组合脚本退出0。Result：`SYNTHETIC_PACKAGED_LICENSED_WORKFLOW_HTTPS_PASS`。Known Issues：完整交接→调研→需求→原型→方案→计划/输出纵向链、真实浏览器、正式公钥/客户License/目标服务账户、法律放行、离线安装升级、UAT和Gate仍未通过。Next：`PKG-PILOT-01-A04-P03` 固定候选的真实浏览器与后续业务路由预检；不能把合成签名或此单片结果称作可用 Pilot。
