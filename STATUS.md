# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`PLT-02-A03 Secret 管理元数据只读查询与权限边界`（已完成）|
|Current Status|PHASE_1_COMPLETE / PLT_02_A03_PASS / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、PLT-02-A01～A03、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、LIC-01-A01～A04、LIC-02-A01～A05、LIC-03-A01～A03 PASS|
|Blockers|LIC-02-A02 的载荷冲突已由 CR-LIC-001 方案 B 解除；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|LIC-03-A03 方案 A 已确定；当前无人工决策待办。客户数据外发、付款/额度重置和不可恢复生产操作不在持续授权内|
|Architecture Version|`ARCH-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，License ADR-006 经用户批准 CR-LIC-001 修订|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，DM-02 License 授权粒度经用户批准 CR-LIC-001 修订|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；SC-01～SC-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）；SC-04 Migration 仅为验证性实现|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|PLT-02-A03：Windows 11/Python 3.13 后端 197/197 PASS；服务覆盖率 97%；PostgreSQL 18.6 临时库管理员/成员权限、脱敏分页和许可拒绝 PASS；wheel 构建 PASS；无公开 API|
|Next WBS|`PLT-02-A04 Secret 加密算法与密文写入边界`；生产密钥来源与恢复另列 Release 安全设计|

## 自动执行策略

- 模式：按 `AI自主执行与最小人工确认规则 V1.1.md` 持续自主执行至可用程序包；偏差先建立 Change Request，再实施、验证并同步 GitHub；Gate 按实际证据关闭，不虚报。
- 代决策授权：用户 2026-09-24 明确授权原方案不兼容时自主分析并执行解决方案，默认接受，不再逐项询问；范围和安全边界见 `docs/changes/CR-EXEC-001-continuous-delivery.md`。客户数据外发、付款/额度重置、不可恢复生产操作和伪造客户确认不在授权内。
- 周额度规则：用户已于 2026-09-23 取消自动检查和 20% 停止线；后续仅在用户明确要求时查询。额度重置或购买仍需逐次明确确认。
- GitHub：允许在当前 Scope 和正确分支内自动 fetch、commit、push；禁止 force push、直接提交 main、覆盖未知远端修改或提交 Secret/客户数据。

## 最近检查点

- 分支：`feature/license-runtime-guard`
- 最近功能检查点：LIC-02-A05 已实现仅内部管理员受控重验证；拒绝状态可在活动安装文档、真实验签、机器/有效期/可信时间全部通过后恢复 VALID，失败则保持拒绝并记录事件/Audit。公开 HTTP 挂载、生产公钥/选定 MAC/可信时间密钥来源与初始化仍未接线，不得对外开放业务。Auth 仍无公开登录或管理 API。
- LIC-03-A03 编码前发现任务名称仅为上一任务暂定，未有批准的验收定义；冻结架构明确把 SecretKeyProvider 的 Windows/Linux 实现与密钥恢复留给 Release 安全设计，当前仅有未落地的 Secret 访问 Port。生产可信来源不能以明文环境变量/普通 YAML/临时文件替代，受影响的装配工作暂停，见 `docs/progress/lic-03-a03-precheck.md`。
- 用户已选择方案 A 并作出持续执行授权：LIC-03-A03 现只做一次性受控初态初始化，生产信任源留待 PLT-02/Release；执行纪律差异见 `CR-EXEC-001`。上条“暂停”记录作为历史检查结论保留，不代表当前仍待用户决定。
- LIC-03-A03 已按方案 A PASS；初始化不包含生产信任源，不能放行业务。下项推进 PLT-02 SecretRecord 数据层；具体跨平台密钥保护与恢复仍待 Release 安全验证。
- PLT-02-A01 已完成密文版本持久层与迁移；生产 Secret Store 仍需写命令、权限/审计、解密适配及跨平台主密钥方案，不能据此配置真实 API Key。
- PLT-02-A02 已完成只读密文信封适配；使用合成解密器验证消费边界，不代表生产加密/解密已可用。管理元数据、正式写命令与跨平台主密钥仍待后续任务。
- PLT-02-A03 已完成管理员元数据内部查询与脱敏投影；公开 GET、生产 License/Secret 装配和写命令未接线。
- LIC-02-A02 冻结冲突已由用户明确批准方案 B；正式差异见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`。V2.1 原文保留历史，专项补充为当前 License 授权粒度基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
