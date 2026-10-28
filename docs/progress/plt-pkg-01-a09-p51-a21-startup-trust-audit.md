# PLT-PKG-01-A09-P51-A21：Windows 应用启动信任前置审计

- 日期：2026-10-28
- 状态：`BLOCKED_BY_MISSING_PRODUCTION_TRUST_RESOURCE`（只读源审计；没有运行产品代码）
- 分支：`feature/p51-embedded-runtime-cache`；PR #55
- 目标：确认 Windows 生产 API 启动链可用的正式信任/凭据前置，不引入测试身份或假造密钥。

## 编码前检查与范围

- 按仓库 `.ai/SKILL.md`、`STATUS.md`、自主执行规则和项目开发 Skill 的既定工作纪律执行；本 WBS 是只读启动前置审计，不修改生产运行代码。
- 单一问题：当前候选父包是否具备在真实生产 License 信任链下启动产品 API 的必要资源。
- 允许证据：当前分支源文件和包资源声明。禁止在用户设备运行程序；本次无程序执行，也没有客户资料外发。
- 偏差：A20 已完成父包与 PostgreSQL 临时生命周期，但没有产品 API。A21 以明确判据验证启动信任缺口，不把基础设施 smoke 扩大解释为应用通过。

## 检查结果

1. `apps/backend/src/plm_assistant/modules/license/infrastructure/packaged_product_key.py` 将固定读取 `trust/product_public_key.json`，验证严格的 JSON schema、产品代码、固定 key ref 以及规范 Base64 Ed25519 公钥；读取、格式或验证失败均抛出统一错误，不提供配置覆盖或 fallback。
2. `apps/backend/src/plm_assistant/entrypoints/windows_license_runtime.py` 的生产 composition 要求数据库已就绪、schema 当前、上述 `PackagedProductKey` 可加载、已选机器 MAC 可读取，以及 Windows trusted-time integrity 可建立。任何异常均转为 `ProductionLicenseStartupError`。
3. 仓库内容 API 查询确认 `apps/backend/src/plm_assistant/modules/license/trust/product_public_key.json` 当前分支不存在（404）；同一模块的正式运行实现和包数据声明要求此资源。
4. 因而当前候选不能构造正式 Windows License 服务，也不能通过该生产登录 composition 声称应用 API 可启动。A20 的 PostgreSQL smoke 只证明临时数据库生命周期，未调用应用 API。

## 结果与处置

- 结果：`FAIL_CLOSED_AS_DESIGNED`，不是通过项。缺失的是正式产品公钥信任锚，不能用测试密钥、临时密钥或猜测值替代，也不能生成开发者私钥补位。
- 不在用户本机执行程序，不请求/外发密钥，不更改 License 信任逻辑。
- 独立后续工作：继续完善 hosted Windows runner 的离线安装包、安装前预检、服务账户/权限配置说明与安全拒绝路径。只有仓库获得受控正式公钥资源后，才能在 hosted runner 对真实打包资源进行集成验收；真实签发和信任授权仍按 License 基线管理。
- 其他尚未验证前置：Windows Credential Manager 数据库凭据接线、服务账户/ACL、HTTPS、OCR 模型与原生组件、重启/备份/升级以及 UAT。不得将其描述为已验证。

## 验证边界

本次仅做 GitHub 源文件和路径存在性审计，没有运行代码或测试。正式 API、真实 License、Windows 服务安装、Pilot、Gate 3～7 和正式 Release 仍未通过。A20 云端候选和 A21 审计证据见 `docs/progress/plt-pkg-01-a09-p51-a20-bootstrap-package-result.md` 与 `STATUS.md`。
