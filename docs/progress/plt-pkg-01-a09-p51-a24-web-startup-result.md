# PLT-PKG-01-A09-P51-A24：Web 与启动链集成实施记录

- 日期：2026-10-28
- 状态：IMPLEMENTED_AWAITING_HOSTED_VALIDATION
- 基线：A24 precheck先行提交596f143f4af74a080d41fa722567f36dd7ccbaa3；前置A23 run 40614113243 PASS_LIMITED
- 变更：同run Windows父包新增Caddy 2.11.4 Windows AMD64官方二进制及其LICENSE/README；官方ZIP、SBOM、源码压缩包与SHA-512清单交由既有审计器校验；父包 manifest/provenance纳入组件版本、摘要和审计报告。Hosted smoke将从父包D盘临时解包启动loopback-only Caddy与临时API探针，验证SPA fallback及 /api/v1 反代并停止两个进程。
- 差异/风险：旧Caddy构建器绑定旧父包布局，因此按precheck单独接入当前父包。许可证审核仍未完成，manifest依然legal_clearance=false/release_eligible=false；不包含TLS证书/私钥，不启动正式产品API，不将合成API探针描述成业务验收。
- 本机资源约束：不在用户设备执行任何程序；工作流下载、打包、解压、服务进程和数据库都限定于GitHub hosted Windows runner。smoke要求runner临时目录为非C盘。
- 验证状态：尚未运行；当前提交后由PR工作流触发全量托管构建与smoke。失败时记录首轮失败并修复后重跑，不计失败run通过。
- 下一步：阅读最新workflow jobs和artifact摘要，核实Caddy/SPA/反代/停止清理/PG回归；据实更新STATUS与结果记录。
