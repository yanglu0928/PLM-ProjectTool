# CR-PKG-005：离线同源 HTTPS 前端/反向代理边界

日期：2026-10-01；状态：`RECORDED / IMPLEMENTATION_AND_RELEASE_EVIDENCE_OPEN`；关联 `PLT-PKG-01-A09-P18-A03`、Gate2冻结架构图、ADR-013、AUT-03-A01/A07、AUT-05-A03、P15～P18-A02。原冻结提交 `64cdf09` 不追写。

## 来源、冲突与证据

冻结架构要求用户经HTTPS边界访问Vue Web与FastAPI，前端使用同源REST/JSON/SSE。当前前端客户端以相对`/api/v1`和`/health`请求，Cookie用`credentials: same-origin`；Vite代理只在开发服务器提供。Windows生产`serve_windows`/SCM API只允许127.0.0.1回环监听且禁用代理头信任，登录的Host/Origin策略要求明确可信对外源。P15组合ZIP含静态dist和回环API，却无独立HTTPS/同源路由、证书供给、静态SPA回退或代理服务生命周期。P18-A02只证明默认健康API与静态文件分别在两个loopback端口返回，**不构成浏览器同源产品入口**。未补边界则正式Cookie/CSRF、安全代理与完整UAT无法验收。

## 方案比较及选择

|方案|评价|
|---|---|
|让现有Uvicorn直接向外监听并兼管静态/TLS|须改已锁的loopback安全边界、静态/证书/重启责任集中到API进程；对当前安全装配侵入大，拒绝。|
|Windows IIS + Debian独立代理|依赖系统可选角色与两套不同安装/运维链，Windows11/Server2025和Debian离线验收成本高；保留备选。|
|Caddy独立同源边界|单一跨平台静态文件/反向代理/TLS能力，API仍仅loopback，三个现有PLM应用服务角色不变；选择为需进一步固定来源、许可和实机验收的发行候选。|

选择**Caddy独立边界候选**是执行路径，不是已经通过的生产依赖或法律结论。其官方文档说明`file_server`、`reverse_proxy`、SPA `try_files`及自有证书/私钥`tls cert key`可组合，默认反代传递原始Host；官方仓库标示Apache-2.0，具体随包版本/通知与组合义务仍需固定和复核。Windows可按官方文档注册独立服务，但这将是Web边界服务，不冒充ADR-013的三项PLM应用服务。Debian13实机按用户指令暂缓，兼容目标不删除。

## 与原基线差异和安全约束

- 在原单机模块化单体外围新增独立Web边界及重要第三方运行依赖；业务模块、数据库、冻结`/api/v1`、三个应用服务角色及AI/License机制不变。将此新增依赖作为正式CR，绝不静默塞入P15包。
- 正式离线安装由实施方供给与外部域名匹配的证书及TLS私钥，按目标账户ACL保管在客户主机；不提交Git/非发行ZIP，不与**仅开发者工作台持有**的License Ed25519私钥混淆。不能依赖公网ACME或静默生成/信任内部CA来假定离线可用。
- `/api/v1/*`及`/health/*`原样转发至127.0.0.1 API，不strip路径，不信任来自外部的转发头；静态SPA回退只在非API路径，不能把未知API错误改写为HTML。对外Host/Origin须与显式`trusted_origins`逐字节匹配；后端仍禁用代理头信任。测试错误源、重复Host/Origin、Cookie Secure/HttpOnly/CSRF与SSE。
- Web边界静态根只读，`data/config/license/logs`不得暴露。证书/私钥的安装、续期、备份和权限由独立安全流程验证，不能用P18合成静态服务器替代。

## 实施、迁移/回滚和验证计划

1. 固定Caddy官方版本、Windows/Server2025/Debian13 x86-64资产及发布Hash/源码/许可；在Git忽略目录做Windows11隔离PoC，先不修改P15历史候选。
2. 生成只含路径/端口/域名占位的离线Caddyfile模板；`caddy validate`及真实loopback HTTPS合成证书PoC验证静态、API、SPA深链、Host/Origin、Cookie/CSRF、SSE、未知API404；合成证书不进入Git/客户包。
3. 若PoC通过，再新建候选版本及精确NOTICE/源码清单，设计目标账户/ACL和Windows服务/Server2025重启/故障/证书恢复；Debian13实机仍按用户暂缓但不能标Release PASS。
4. 与既有服务/API/PG备份升级联测，实际浏览器和权限/性能/安全验收后方可考虑Gate；任一无法满足，保持发行阻断并按本CR备选方案另记修订。

原P15/P17/P18产物保留；回滚仅停用**尚未投产**的独立边界候选与新候选ZIP，恢复旧非发行包/开发代理，不改API/Schema/客户数据。若已投产，必须先按人工备份/维护/服务静止流程执行，不承诺自动回滚。

## 剩余风险

当前已固定Caddy Windows AMD64输入但尚无发行许可复核、客户证书/目标账户、Windows Server2025实际服务或Debian实机环境；Ghostscript公开源码/产品许可另有独立阻断。此CR不改变P15`release_eligible=false`或Gate状态。

2026-10-01/P19～P20增量证据：官方Caddy v2.11.4 Windows AMD64四资产/源码/SBOM输入已固定，隔离合成HTTPS静态/API/SPA路由通过，但对显式不可信Host的首页请求仍返回200。曾试的额外Host匹配未证明拒绝，故不纳入正式配置；须在P21查清Caddy/HTTP请求语义及生产登录Host/Origin边界，再验Cookie/CSRF/SSE。其他发行风险不变。

官方依据：[Caddy许可仓库](https://github.com/caddyserver/caddy)、[反向代理及Host处理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)、[静态文件](https://caddyserver.com/docs/caddyfile/directives/file_server)、[SPA与API路由](https://caddyserver.com/docs/caddyfile/patterns)、[自有TLS证书](https://caddyserver.com/docs/caddyfile/directives/tls)、[Windows服务](https://caddyserver.com/docs/running)。
