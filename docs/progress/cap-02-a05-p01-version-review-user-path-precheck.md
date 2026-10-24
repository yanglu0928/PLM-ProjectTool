# CAP-02-A05-P01：标准能力版本与正式评审用户路径前置核查

日期：2026-10-24；状态：`PRECHECK_COMPLETE / NO_NEW_RUNTIME_PASS`。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `CAP-02-A05-P01`；只核查当前批准能力版本所需用户操作、已装配 API 和缺口，拆为独立可验收任务；不创建假批准事实。|
|输入基线|Gate 2 冻结 `/api/v1`，CAP-01 后端 Windows 显式组合、CAP-02-A03/A04 Win11 包内合成正向上传→基线身份证据。|
|前置任务|当前仅有 GLOBAL `STANDARD_CAPABILITY` 固定文档与 `ACTIVE` 基线身份；`current_approved_version_ref=null`。不能供交接分析版本引用。|
|涉及模块/实体/API|Evidence `POST /api/v1/global/evidence`、资格决定；CapabilityVersion/Item `POST .../versions`、`:validate`、`:submit-review`；统一 Review Engine 及当前批准指针。|
|涉及权限|GLOBAL Evidence 与 Capability 写操作均要求当前 DeploymentAdmin/Session/CSRF/License；评审使用 `DEPLOYMENT_ALL_V1`，提交时 1～32 名审核人须经当前资格复核，不能由前端仅凭账户列表推定；AI 建议与测试账号不得视作真实人工批准。|
|验收标准|先补 Evidence 真实创建与人工作资格确认；再从已批准 Evidence 和同一固定来源建立至少一条完整 CapabilityItem 的 DRAFT 版本，独立验证现时来源，送审、不同合格管理员处理直至正式当前批准指针，最后 Win11 Edge/隔离 PG 合成验收与拒绝矩阵。|
|风险|Evidence 精确页/段定位当前未开放，创建端仅可证明整份文档 `locator_type=DOCUMENT`；不把整文档指针宣传为精确引用。版本服务强制每项 1～100 个 DocumentRef、1～200 个同源 `ELIGIBLE` EvidenceRef、整版本文档集合哈希与基线固定来源一致；不能用 CANDIDATE/INELIGIBLE、PROJECT Evidence 或伪造 ID 绕过。|

## 静态事实与实施顺序

1. 后端 GLOBAL Evidence 创建已在 Windows 显式写模式装配，返回 `CANDIDATE`；同源 Document 下载校验与实际内容指纹由服务端负责。当前前端 `GlobalEvidenceListView` 有列表/资格决定，但没有 Evidence 创建客户端或页面。首先独立做 `EVD-05-A01`：部署管理员从 GLOBAL 已可用固定文档选择来源，输入整文档标签，创建候选并跳转现有资格页面；禁止自动置 `ELIGIBLE`，保留原幂等号和失败恢复。
2. `CAP-02-A05-P02`：仅实现严格 Version POST 客户端及 DTO/回执测试，使用现有基线 ETag、CSRF 和同号恢复；不在客户端合成 EvidenceId。
3. `CAP-02-A05-P03`：版本/能力条目编辑页从当前 GLOBAL 文档与 `ELIGIBLE` Evidence 元数据选同源固定引用，至少一条完整能力项；需现时来源复核、分页、会话变化清屏，保存后仍仅 DRAFT。
4. `CAP-02-A05-P04`：版本 VALIDATE 与 `DEPLOYMENT_ALL_V1` 正式 Review 发起/处理入口，复用统一 Review Engine 的权限与结果，不把按钮点击或合成批准当客户事实。
5. `CAP-02-A05-P05`：Win11 固定非发行包内真实 Edge/隔离 PG 正向与权限/来源/失效许可负例；待当前批准版本证据成立再回 `HND-05-A02`。这些步骤均不豁免正式信任、安装、UAT、Gate 3～7 和三平台发行。

本片仅静态核查已存在的接口、服务约束、装配与前端路由，没有改产品程序、Schema、冻结 API，也没有运行新业务测试。下一项 `EVD-05-A01` 编码前重新检查其独立输入和验收条件。
