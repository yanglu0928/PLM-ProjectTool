# 项目状态

|字段|当前值|
|---|---|
|Current Phase|Phase 2：Platform Core|
|Current WBS|`PLT-02-A07-P05-A04 Secret 轮换/停用持久幂等`（内部事务/真实 PostgreSQL 并发已验证；写 HTTP 未开放）|
|Current Status|PHASE_1_COMPLETE / PLT_02_A07_P05_A04_WIN11_PASS / PLT_02_A07_P03_A03_CEREMONY_PENDING / PHASE_2_IN_PROGRESS|
|Completed Phases|Phase 0 技术验证（`COMPLETE_WITH_APPROVED_ALTERNATIVES`）；Architecture / Data Model / DB Schema / API Contract Freeze；Gate 2 `APPROVED`；Phase 1 基础工程|
|Completed WBS|POC-01、POC-02、POC-04、POC-05、POC-06、POC-08、POC-09 已按验证或批准例外收口；POC-03 以批准替代方案收口；Gate 1 已通过；AF-01～AF-05、DM-01～DM-06、SC-01～SC-05、API-01～API-05 PASS；Gate 2 已批准并冻结四份基线；1.01～1.09、PLT-01-A01～A03、PLT-02-A01～A06、API-RUNTIME-01（仅 Win11）、PRJ-03-A01～A04、AUD-01-A01～A03、AUT-01-A01～A03、AUT-02-A01～A05、AUT-03-A01～A06、AUT-03-A07-P01～P03（P02/P03 仅 Win11）、AUT-03-A08～A10（仅 Win11）、PRJ-01-A01～A06、PRJ-02-A01～A04、LIC-01-A01～A04、LIC-02-A01～A05、LIC-03-A01～A03 PASS|
|Blockers|AUT-03-A07 Windows 11 合成端到端已通过，Server 2025 目标运行账户/HTTPS 代理与 Debian 安全凭据来源未验证；PLT-02-A07 公开接线待正式发行公钥、目标账户可信时间密钥、生产 License/Secret 装配、If-Match/管理权限与 Server 2025 恢复演练；POC-03 质量失败继续阻塞 Gate 3/UAT，Server Office、Debian 未验证和 Ghostscript 发行合规继续作为 Release 约束|
|Pending User Decisions|LIC-03-A03 方案 A 已确定；当前无人工决策待办。客户数据外发、付款/额度重置和不可恢复生产操作不在持续授权内|
|Architecture Version|`ARCH-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，License ADR-006 经用户批准 CR-LIC-001 修订|
|Data Model Version|`DATA-MODEL-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`，DM-02 License 授权粒度经用户批准 CR-LIC-001 修订|
|DB Schema Version|`DB-SCHEMA-CANDIDATE-V1`；Gate 2 原冻结内容 `64cdf09`；Auth 限流增量 `20260925_0012`，PRJ-01～03 正式实现 Migration `20260925_0013`，成员变更历史增量 `20260925_0014`（CR-PRJ-001），通用幂等收据增量 `20260925_0015`（CR-API-001）|
|API Contract Version|`API-CONTRACT-CANDIDATE-V1`；API-01～API-05 PASS，Gate 2 已冻结（内容提交 `64cdf09`）|
|Test Summary|PLT-02-A07-P05-A04：Windows 11/Python 3.13 后端 366/366 PASS，PostgreSQL 18 临时库同 Key 并发轮换/停用各只一次状态/审计变更及开发 wheel PASS。正式目标账户/发行信任锚未供给，Secret 写路由仍关闭|
|Next WBS|PLT-02-A07-P05-A05 Secret write-only 创建 HTTP，然后轮换/停用；真实发行公钥/目标账户密钥、Server 2025 和 HTTPS 部署仍待；Debian 13 暂不验证|

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
- PLT-02-A04 已完成版本化 AES-256-GCM 加解密适配和临时库密文写入验证；生产 Key Provider、正式权限写命令和轮换仍未接线。
- PLT-02-A05 已完成仅内部受控创建/轮换与同事务审计；生产 Key Provider、公开管理 API、停用命令及 License 整体接线仍未完成。
- PLT-02-A06 已完成内部停用并验证停用后受控读取拒绝；公开管理 API 因生产身份/许可/密钥装配与 If-Match/幂等缺口拆至 A07，当前不可开放。
- PLT-02-A07 前置核查未通过，见 `docs/progress/plt-02-a07-precheck.md` 与 CR-PLT-003；该单项公开接线停留在 404，项目转先完成 AUT-03 等前置，不将 A07 标为 PASS。
- PLT-02-A07-P04-A01 已完成可选挂载的 Secret 详情只读 HTTP 与安全投影/ETag 合成契约；生产管理路由尚未装配，列表/写接口和真实信任锚仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A02 已完成可选 Secret 列表 HTTP/完整性保护游标及 PostgreSQL 同时间戳 keyset 验证；生产游标签名密钥来源/恢复、只读路由装配与写接口仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A03 已完成 Windows 独立游标签名密钥安全来源与临时 Vault 备份恢复测试；正式账户供给与生产只读路由装配仍待完成，A07 整体未 PASS。
- PLT-02-A07-P04-A04 已新增 Windows 显式平台组合，仅在正式 License/游标信任源齐备时挂载 Secret 详情/列表；合成失败关闭通过但正式公钥/账户尚缺，不能把 `--platform` 标为生产 PASS，写 API 仍关闭。
- PLT-02-A07-P05-A01 已修正内部轮换版本条件为记录 `lock_version` 并经 PostgreSQL 版本分离/并发验证；公开 If-Match/幂等尚未接线，写路由仍关闭。
- PLT-02-A07-P05-A02 已增加规范强 If-Match 解析并验证 428/400 安全边界；尚无完整写路由或同事务幂等，不能标 Secret 写 API PASS。
- PLT-02-A07-P05-A03 已完成内部 Secret 创建同事务持久幂等，PostgreSQL 顺序/并发/回滚通过；轮换/停用收据与公开 write-only HTTP 仍待完成。
- PLT-02-A07-P05-A04 已完成内部 Secret 轮换/停用持久幂等与 PostgreSQL 同 Key 并发验证；write-only HTTP 和正式生产信任源仍未完成。
- AUT-03-A01 仅完成未挂载的可信 Host/Origin 策略；缺失/重复/不匹配失败关闭。限流、凭据、Cookie/CSRF 与公开登录仍待后续任务。
- AUT-03-A02 完成 PostgreSQL 原子登录限流；真实客户端地址可信代理策略和过期桶清理调度未接线，登录仍未公开。
- AUT-03-A03 完成内部登录编排与真实 scrypt/Session 集成；公开 HTTP/Cookie/CSRF、初始管理员和生产装配仍未完成。
- AUT-03-A04 完成可选登录 Router 的 Cookie/CSRF 传输契约；未注入生产依赖时仍 404，不能视作可用登录。
- AUT-03-A05 补齐 SessionView 身份/部署角色并强制显式 Project 授权摘要 Port；项目成员读层未实现，生产 Router 仍未装配。
- AUT-03-A06 提供仅空 User 表的一次性本机初始管理员 CLI；测试库验证成功，但未在真实部署替用户设置密码或创建管理员。
- AUT-03-A07 生产装配前置未满足，按 CR-AUT-002 先建设当前 Phase 2 的 Project 成员事实，未将 A07 记 PASS。
- PRJ-01-A01 三张 Project 表与约束已落地；该任务本身不包含业务命令或授权读取，后者已由 A02 补充只读摘要。
- PRJ-01-A02 建立当前 ProjectMember 事实的只读授权摘要；逐操作授权及生产登录安全配置仍未完成。
- PRJ-01-A03 完成 13 项 Project 路径内逐操作授权与目标归属核查；Project 列表/创建及实际写命令、生产 Auth/License 装配仍未完成。
- PRJ-01-A04 完成仅内部原子创建 Project、首位 Manager 与默认/指定 Department；真实 Auth Session/CSRF 已接，License Guard 在临时库仍为合成依赖，公开路由未开放。
- PRJ-01-A05 完成内部当前 Session/成员驱动的 Project 列表与详情读取；归档受权可读，跨项目隐藏，公开 GET 与生产 License 装配仍未完成。
- PRJ-01-A06 完成内部项目名称修改与单向归档，按当前管理角色和 expected version 串行化并同事务审计；跨模块归档写拦截及公开 API 仍需后续接线。
- PRJ-02-A01 完成内部授权成员历史列表与 keyset 分页；公开 HTTP 的不透明 cursor、生产 License 与安全运行接线仍未完成。
- PRJ-02-A02 完成内部成员创建与单项目并发唯一性验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A03 按 CR-PRJ-001 完成内部成员角色/部门修改与历史保存；正式 PATCH 的 HTTP If-Match/幂等、生产 License 与公开 API 仍未接线。
- PRJ-02-A04 完成内部成员暂停/恢复/移除与最后负责人保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- PRJ-03-A01 完成内部授权部门历史列表和稳定分页；正式 GET 不透明 cursor、生产 License 与公开 API 仍未接线。
- PRJ-03-A02 完成内部部门创建、活动编码唯一与并发冲突验证；正式 POST 幂等、生产 License 与公开 API 仍未接线。
- PRJ-03-A03 完成内部部门名称/编码 PATCH、强版本与并发冲突验证；现有 Audit 不保留字段级旧值，正式 PATCH/生产 License 与公开 API 仍未接线。
- PRJ-03-A04 完成内部部门单向停用与 ACTIVE/SUSPENDED 成员引用保护；正式 POST 幂等/If-Match、生产 License 与公开 API 仍未接线。
- LIC-02-A02 冻结冲突已由用户明确批准方案 B；正式差异见 `docs/changes/CR-LIC-001-single-product-full-bundle.md`。V2.1 原文保留历史，专项补充为当前 License 授权粒度基线。
- 远端同步状态必须在每次任务结束前通过 Git 实时检查，不在本文件固化可能过期的 ahead/behind 数值。
- 本地用户文件和 Git 忽略的客户资料保持不变。
