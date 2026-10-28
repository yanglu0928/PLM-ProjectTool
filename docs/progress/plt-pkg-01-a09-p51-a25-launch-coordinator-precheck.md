# PLT-PKG-01-A09-P51-A25：受限 Windows 启动协调器编码前检查

- 日期：2026-10-28
- 当前 Phase：Phase 2 Platform Core；Windows 11 内部试用包关键路径
- 当前 WBS：PLT-PKG-01-A09-P51-A25
- 输入基线：A24 hosted Windows run 40617690473 PASS_LIMITED；当前父包包含嵌入式 Python、Windows API入口、静态 dist、Caddy 2.11.4、PG18候选；Release规则要求公钥/License信任、Credential Vault、TLS、服务账户/ACL及离线安装齐备后才可开放
- 前置任务：A23缺凭据 fail-closed 与A24 Caddy loopback SPA/代理 smoke均已hosted验证；A24全量CI仍以非发行候选标记
- 涉及模块：Windows 候选启动编排与Web/Caddy进程管理；不改业务模块或服务API
- 涉及实体：父包manifest、非敏感bootstrap配置、进程句柄、Health状态
- 涉及API：不改冻结API；只等待现有本地 /health
- 权限：不新增业务权限。数据库口令只允许由应用已批准的Windows Credential Manager来源读取；启动脚本/日志不得读取或输出凭据内容
- 编码前证据：serve_windows.py 只接受本地bootstrap文件与受限平台模式；把uvicorn/API绑定到loopback；异常以固定消息fail closed。当前父包 startup_preflight 始终formal_startup_ready=false，阻断码FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED。Caddy正式模板需要目标侧提供TLS证书和私钥；A24 smoke仅HTTP loopback及合成handler。
- 本WBS目标：增加包内Windows启动协调器。启动前验证manifest不声称正式就绪、运行目录与配置/证书边界；按先API后Edge顺序启动，只有API健康且所需TLS材料可用才允许Caddy打开HTTPS listener；任何失败停止已启动子进程并返回非零。启动器不得生成或替代密钥/License，不读出凭据内容，不把密钥放进命令行/环境变量。
- 当前限制下的验收标准：在hosted Windows D盘副本中，manifest显示正式阻断时启动器在任何listener之前拒绝；缺配置、缺TLS材料、异常进程、API health timeout等拒绝分支均不遗留进程/端口；启动器/manifest仍不含Secret，父包hash readback通过。由于正式公钥/License信任未提供，本任务不要求也不得伪造生产成功启动验收。
- 涉及差异：旧候选没有统一受控启动器；由独立PowerShell启动脚本协调嵌入Python入口和Caddy，复用现有拒绝条件，不改API/License冻结合同。交付仍为NOT-FOR-RELEASE候选。
- 风险：Credential Manager API初始化、目标账户TLS材料/ACL、正式产品公钥/License和真实API健康链未在本环境提供；因此只做受控拒绝验收。Caddy第三方法务评审未完成。
- 迁移：无数据库变化；旧父包格式不变，新同run父包多一个启动脚本/模板清单。
- 回滚：删除新启动脚本和对应manifest entry即可回到A24候选；不动持久化/安装数据；Actions artifact短期保留。
- Secret检查：不输出credential、API key、License签名数据、证书、私钥、环境变量或日志内容；拒绝把.pfx/.p12/.key/.pem/.env放入候选包。
- 运行边界：只通过 GitHub hosted Windows 2025；所有新工作、过程、缓存和数据放runner D盘临时目录，不在用户本机执行。

## 实施前风险与验证计划

1. 在manifest明确未就绪时必须在spawn API/Caddy前拒绝。
2. 有效manifest但配置不合法时仍不得spawn任何子进程。
3. API启动后health timeout或API提前退出时，Edge不得启动，API必须终止并等待。
4. Edge启动后进程异常/退出必须能停掉API；正常停止两个进程必须等待，超时后有限kill。
5. 使用本地临时HTTPS证书只做hosted候选证书测试时，证书/私钥仅临时runner D盘文件，永不作为package input/artifact上传；当前未实现正向路径，不用合成证书伪装正式信任。
6. 工作流全量构建、D盘解包与launcher拒绝路径回归通过后，才将任务写为PASS_LIMITED；正式启动保持BLOCKED/NOT_READY。
