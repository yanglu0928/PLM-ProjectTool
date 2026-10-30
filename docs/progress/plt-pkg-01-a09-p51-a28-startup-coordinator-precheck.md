# PLT-PKG-01-A09-P51-A28：受限 Windows 启动协调器编码前检查

- 日期：2026-10-29
- 当前 Phase：Phase 2 Platform Core；CR-EXEC-002 Windows 11 内部试用包关键路径
- 当前 WBS：PLT-PKG-01-A09-P51-A28
- 前置：P51-A25启动守门、A26候选暂存和A27包内PlanVersion Edge/HTTPS/PG均为PASS_LIMITED；A27最终 hosted run 40841364426。
- 当前证据：A25包内 start-trial.ps1 仅检查非发行manifest及 formal_startup_ready、公钥标志和阻断码，随后固定拒绝；父包 manifest 未携带受控DB credential target/TLS deployment readiness 事实。A25验收证明缺失正式信任时不开放listener；正向启动路径刻意未实现。
- 输入基线：父包 manifest v1、bootstrap.example.yaml、A25固定fail-closed启动入口、A24 loopback Caddy与合成API smoke、release-rules.md。当前 manifest release_eligible=false/legal_clearance=false，缺正式产品公钥；真实服务账户、目标ACL、受控DB凭据/TLS证书均未提供。
- 单一目标：在包内启动入口对父包信任、服务身份/凭据引用和TLS配置做明确、类型严格的前置守门；任一缺失/歧义时于启动API/Caddy之前拒绝，确保不打开listener、不读出凭据/私钥内容。仅对现有未就绪父包做真实拒绝验收，不模拟正式信任、不验证正向生产启动。
- 涉及范围：Windows父包manifest/非秘密启动配置、start-trial.ps1及其独立验证器/测试、Hosted Windows工作流和结果文档。无业务API、数据库Schema/Migration、权限、License实现或正式配置内容变化。
- 实体/API/权限：无业务实体/API/权限变化；仅验证当前产品包和本轮自有临时进程/文件。
- Secret边界：不调用Credential Manager读取secret blob；仅允许核对固定target引用/存在性状态。不得打包、输出或上传真实Credential、TLS私钥、证书文件、License材料及日志。证书/私钥将来由受控部署侧提供，但本项不得伪造或引入。
- 验收：hosted Windows Server 2025 D盘RUNNER_TEMP；对当前实际父包执行清洁提取和manifest逐项摘要验证；启动入口在任何子进程/端口前拒绝正式信任缺失、credential引用缺失、TLS配置缺失、格式/路径越界等情形；stdout为空且输出固定错误；loopback端口无listener；Caddy/API/PG均未残留；仅清理本run拥有的临时根并复核候选摘要。
- 迁移/回滚：无数据库迁移、无已安装产品变化。回滚删除A28新启动检查和manifest非秘密元数据，恢复A25 fail-closed固定guard；旧候选/安装数据不动。
- 风险/限制：没有正式公钥/License trust、服务账户Vault/ACL和TLS deployment，故不能安全验证正向启动；A28最多PASS_LIMITED，不能关闭Pilot/Gate 3/正式Release，也不能推断Windows 11设备兼容。
- 执行方式：所有代码与程序仅由GitHub hosted Windows runner执行；Runner temp/解包/日志均显式放D盘RUNNER_TEMP后代。不在用户本机及C盘运行项目代码。

## 编码前结论

当前输入、模块、信任边界及验收约束已核实；A28可在现有真实缺信任状态下完成可审计的 fail-closed 守门，不依赖用户本机或外部数据。开始编码前，先保持当前分支HEAD和远端状态一致，并沿用既有合成父包/临时资源工作流。

## 首轮云端验收偏差（2026-10-29）

- Hosted run 40847373608 中新增启动前置字段的定向 unittest、父包同源构建、A17 harness守门通过；D盘PG smoke在 exact startup_preflight assertion 处失败。
- 实际父包生成字段与预期一致；旧 smoke validator仍只接受A25三字段（formal_startup_ready、公钥存在、仅公钥阻断），不认识A28新增License trust、数据库Credential target引用、服务身份ACL、TLS cert/key字段。失败发生在启动guard调用前；未启动API/Caddy/PG，不能作为A28验收。
- 偏差仅在兼容性断言范围；按预先记录方案，将 smoke expected startup metadata更新为新完整schema，并继续检查当前所有阻断字段为false、manifest/verification summary完全一致、固定拒绝及无listener。不得放宽拒绝条件，不修改产品业务/API。
- 首轮run不计通过；本记录先行登记，随后仅在hosted runner复验。
