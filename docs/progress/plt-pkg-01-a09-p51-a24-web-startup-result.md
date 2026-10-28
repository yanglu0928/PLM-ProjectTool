# PLT-PKG-01-A09-P51-A24：Web 与启动链集成实施记录

- 日期：2026-10-28
- 状态：PASS_LIMITED（候选包Web静态服务与合成API反代通过；正式产品API/HTTPS/安装仍未验证）
- 基线：A24 precheck先行提交596f143f4af74a080d41fa722567f36dd7ccbaa3；前置A23 run 40614113243 PASS_LIMITED
- 变更：同run Windows父包新增Caddy 2.11.4 Windows AMD64官方二进制及其LICENSE/README；官方ZIP、SBOM、源码压缩包与SHA-512清单交由既有审计器校验；父包 manifest/provenance纳入组件版本、摘要和审计报告。Hosted smoke将从父包D盘临时解包启动loopback-only Caddy与临时API探针，验证SPA fallback及 /api/v1 反代并停止两个进程。
- 差异/风险：旧Caddy构建器绑定旧父包布局，因此按precheck单独接入当前父包。许可证审核仍未完成，manifest依然legal_clearance=false/release_eligible=false；不包含TLS证书/私钥，不启动正式产品API，不将合成API探针描述成业务验收。
- 本机资源约束：不在用户设备执行任何程序；工作流下载、打包、解压、服务进程和数据库都限定于GitHub hosted Windows runner。smoke要求runner临时目录为非C盘。
- Hosted Windows workflow：run 40617690473，PR #56 head 6b02ce9124f8388ac5b3dd7d8b716e3457d58330；7/7 jobs success。父包artifact 12786700078（Actions artifact ZIP 372,572,250 bytes）；内部候选ZIP 379,027,780 bytes，SHA-256 609cf8b0567f1ad13b800a7a9be2fd5c6b1a954471d57e01d13d847e90c09ef3，20,117 payload项。Smoke artifact 12786372270，runner D盘，PG18.6/pgvector0.8.6临时生命周期及A23缺凭据fail-closed回归均通过；Caddy loopback static SPA与/api/v1合成反代通过并清理两个进程。
- 结果边界：本项仅证明受限候选的Web静态服务和合成API路由；HTTPS、正式服务端证书、真实产品API成功启动、服务账户/ACL、安装升级、OCR、完整业务链、UAT、Gate和Release均未通过。生产公钥仍缺，manifest继续legal_clearance=false/release_eligible=false。
