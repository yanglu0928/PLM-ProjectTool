# 当前非发行候选的发行阻断清单

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P46-A01`；结论：`RELEASE_BLOCKED / EVIDENCE_REGISTERED`。本清单供项目负责人确定关闭顺序，基于固定 Windows 11 原生 OCR 通知候选及仓库现有验收记录；它不是法律意见、Gate 通过记录或正式发行批准。

只读打开本地 ZIP 并计算 SHA-256，得到 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`、载荷 21,158 项；manifest 中 `release_eligible=false`、`legal_clearance=false`、`formal_tls_material_included=false`，库存和原生 OCR 材料均为 `REVIEW_REQUIRED`。ZIP 根目录没有产品级 `LICENSE`/`NOTICE`；`payload/runtime/LICENSE.txt` 是运行时文件，不能误记为产品级许可证。P45-A03～A07 已证明来源、清洁解包、布局、合成 HTTPS 与随包合成登录链，不能外推为正式安装或发行。

## 阻断项与关闭证据

|范围|当前证据与状态|关闭该项所需的证据|可立即推进的工作|
|---|---|---|---|
|第三方发行与产品通知|[P43 发行材料分类](plt-pkg-01-a09-p43-a06-release-obligation-delta.md)和[当前候选侧载](plt-pkg-01-a09-p45-a03-native-ocr-notice-candidate.md)已有 Caddy/Go/Ghostscript 源码及原生 OCR 42 份正文、61 条映射；产品级 LICENSE/NOTICE 仍缺，所有法律标志未放行。|逐组件确认归属、许可适用、对应源码与通知；形成与固定发行物字节一致的产品级 LICENSE/NOTICE，并留有合格审阅人、版本、日期和结论。AI 不替代法律签核。|以新候选为基准更新第三方 NOTICE 审阅稿和缺项队列；保持 `release_eligible=false`。|
|正式 License 与安全信任源|[正式信任源前置核查](plt-02-a07-p05-a09-release-trust-precheck.md)记载工作台真实签发仪式、独立备份、目标账户密钥来源未完成；[P45-A07](plt-pkg-01-a09-p45-a07-native-ocr-notice-packaged-login.md)只用合成公钥/Vault。|工作台操作员保管真实私钥/强口令和独立备份；发行公钥进入包，目标账户可信时间/Secret/游标密钥可恢复，真实 License 与启动/失密/恢复演练通过。|整理操作员仪式、目标账户和故障恢复验收输入；不得把合成私钥当正式来源。|
|Windows 11 正式安装与升级|P45-A04～A07 仅为 Temp 清洁解包、布局及回环合成测试；正式根、SCM、既有数据库未动。|按发行规则在断网目标完成新装、重启、License、项目、AI 配置、OCR、输出；旧版备份、维护模式、离线升级、Migration 与人工恢复演练；Regression/Permission/Performance/Plugin/AI-RAG Gate。|继续完善无破坏性的安装/升级验收脚本与前置清单，待正式信任/法律材料齐备后执行。|
|Windows Server 2025|[VM 前置核查](plt-pkg-01-a09-p44-a01-server2025-nat-precheck.md)仅证明虚拟机可启动/关机；宿主 VMnet8 地址漂移，管理通道不通，目标安装未开始。[CR-ENV-001](../changes/CR-ENV-001-vmnet8-host-address-recovery.md)未实施。|具备宿主管理员权限和维护窗口后恢复 NAT 地址并核对其他 VM 影响；再验证来宾连通、目标账户/ACL、正式 HTTPS/License、离线新装与恢复。|网络修复前继续不依赖该 VM 的工作；不得用 Windows 11 结果推定 Server PASS。|
|Debian 13|用户批准的[Phase 0 例外](../poc/phase-0-exceptions.md)仅暂缓本轮执行，不删除正式兼容目标；本项目尚无 Debian 13 发行验收。|若要声称 Debian 兼容或交付 Debian 包，仍需对应离线安装、License、Plugin、输出和升级证据；当前维持 `DEFERRED_BY_USER / 未验证`。|保留目标与缺口，不制作“已验证 Debian 发行包”。|
|AI/RAG 质量与 Gate 3|[POC-03 例外](../poc/phase-0-exceptions.md)保留分类 24/50（48%）和引用 37/50（74%）失败；R11 离线修复不等于真实质量 PASS。|在未参与调优的全新独立留出集复验，达到分类 90%、精确引用 98% 等原门槛；如需向外部模型发送新正文，须当轮明确授权具体范围。|可先本地整理新留出集与错误分类，不外发客户正文，不改写历史失败。|
|正式 Release Gate 与交付件|[发行规则](../../.ai/skills/plm-project-development/references/release-rules.md)要求 Regression、Installation、Upgrade、Permission、Performance、License、Plugin、AI/RAG 及平台包/手册/清单；现有合成测试不是全项验收。|逐门禁真实记录 PASS、版本一致的发行包/数据库/插件/工具/手册/Release Notes 与验收报告，再从 `release/*` 同步。|建立逐门禁证据索引；任何缺证据均保持未通过。|

## 关闭顺序与执行边界

先完成不依赖外部环境的第三方材料归属和产品 NOTICE 审阅输入、正式安装/升级前置清单及新留出集准备；这些工作不提升 Gate。工作台真实密钥仪式、法律签核、宿主管理员网络修复及当轮客户数据外发授权分别由具备相应权限的人完成后，再进行目标环境安装、质量复验和最终发行验收。任一门禁缺证据时继续保持 `release_eligible=false`，不将此清单本身作为放行凭证。
