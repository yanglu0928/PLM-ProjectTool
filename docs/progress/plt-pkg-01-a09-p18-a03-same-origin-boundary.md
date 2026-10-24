# PLT-PKG-01-A09-P18-A03：前端同源API与HTTPS边界核查

日期：2026-10-01；状态：`DEPLOYMENT_GAP_CONFIRMED / CR_PKG_005_RECORDED / NO_PROXY_INSTALLED`。

编码前检查：Phase2/Gate3开放；输入为冻结架构HTTPS边界、前端相对`/api/v1`/`/health`调用及同源Cookie、AUT-05-A03仅开发Vite代理、后端回环/Uvicorn/Host-Origin策略、P15/P17/P18-A02实际包。此项只核部署合同并先登记发行依赖CR/决策；不修改业务/API/Schema/权限、现有安装、服务或客户数据。验收：识别开发代理与正式代理的差别、固定安全要求/替代路径及可验证下一项；不得把两端口健康/静态服务报告为产品同源HTTPS。

结果：P18-A02的前端静态文件与默认API在不同loopback端口分别可用，但前端`credentials: same-origin`及相对路径要求一个共同浏览器Origin；Vite代理只在开发态。现有正式入口仅回环，故当前组合包缺对外HTTPS终止、同源静态/`/api/v1`/健康路由和服务生命周期。按持续授权已在**实施前**建立[CR-PKG-005](../changes/CR-PKG-005-offline-same-origin-https-boundary.md)并记录DEC-566，比较直接Uvicorn暴露、Windows/IIS+Debian代理和跨平台Caddy，选择后者作为需PoC/来源/许可/证书/目标平台复核的独立发行候选；尚未下载、安装或并入P15包。

官方文档仅证明Caddy提供所需静态/反代/TLS构件并标示Apache-2.0，不证明本项目组合安全或法律发行已通过。下一项固定官方离线二进制/Hash与许可来源，在隔离环境验证带**合成证书**的同源HTTPS路由；正式证书/客户私钥须由实施方目标账户供给且不得进入Git。后端仍只回环、禁代理头信任并校验真实外部Host/Origin。Debian13按用户指令暂缓实机，目标不删除。`release_eligible=false`、Gate3～7开放。
