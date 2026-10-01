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

2026-10-01/P21-A01纠正与实施：P20仅采集错误Host状态码；最小回显探针证明该200为空正文，原“首页返回”结论撤回。按本CR的显式拒绝要求，在固定`localhost`站点外增同端口无主机名兜底站点返回421；重复Host由HTTP服务器拒绝400。固定包21,103件重验及合成HTTPS完整重跑通过；该结果仅覆盖合成回环Host路由，不涵盖生产登录/Origin/证书/目标账户。

2026-10-01/P21-A02增量证据：固定包与Caddy字节审计后，在唯一临时PG18/Windows Vault目标上，以真实生产登录组合根通过合成Caddy HTTPS做登录/Session/审计原断言及错误Host421、错误Origin403、Cookie Secure/HttpOnly/SameSite、缺CSRF403；临时库/角色/Vault与子进程清理回读。SSE、正式证书/License、目标账户/Server2025/Debian、NOTICE和UAT仍未验。

2026-10-01/P21-A03增量证据：固定Caddy合成HTTPS对内存注入的纯测试SSE路由完成首帧完整/非延迟转发、no-cache、错误Host421、客户端断线后上游取消；不等于产品实际AI SSE验收。正式证书/账户、NOTICE与三平台发行门禁仍开放。

2026-10-01/P22增量证据：新非发行ZIP在P15原21,103项外，逐件加入Caddy可执行文件/许可/README/SBOM/checksums/buildable source及占位模板，共21,110项；整包及独立逐件验证通过。原P15不覆盖，未装服务或证书；完整NOTICE/其他组件源码义务、模板目标渲染和正式发行仍开放。

2026-10-01/P23增量证据：P22 ZIP全新ASCII Temp清洁解包21,110件、落盘/源包重核通过，包内模板以合成证书和随机端口渲染通过真实Caddy validate/同源HTTPS静态/API/SPA/错误Host421。正式域名证书、目标ACL/账户及SCM安装仍未执行。

2026-10-01/P24增量证据：固定ZIP 21,110载荷+3清单建立21,113条确定性目标映射（SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`），Windows大小写冲突0。Caddy候选独立Web边界与ADR-013三应用服务分开；真实账户、证书来源/ACL、许可法律及服务恢复仍保持门禁。本项纯只读，未把文件放入正式安装根或注册SCM。

2026-10-01/P25增量证据：在独立ASCII Temp布局复制/读回P22全21,113目标，来源ZIP/清洁暂存末次重验；OCR模型、嵌入式Python/PG/Caddy版本及合成证书模板实际`caddy validate`通过。该布局未做HTTPS真实网络、登录、目标账户/证书或SCM服务测试，仍非发行；`C:\PLMTool`不变。

2026-10-01/P26-A01增量证据：P25隔离布局21,113目标全量Hash重验后，以包内Caddy/API和合成证书实际HTTPS验证静态首页/两项资源、健康200、默认API404、SPA深链200、错Host421；子进程及临时证书清理。生产登录/Session/CSRF/审计尚未在新布局复验，留P26-A02，不因本项静态烟测关闭认证门禁。

2026-10-01/P26-A02增量证据：新布局Hash重验后，以布局内Caddy及PG18、临时Vault目标/合成HTTPS复用原生产登录组合断言，GET9/POST12、Cookie/CSRF/Host/Origin、Session/Project/Audit通过并完成临时源清理。API应用对象仍由仓库验证代码构建，并非包内生产模式进程；不可据此关闭随包生产信任源与正式安装门禁。

2026-10-01/P32后续来源规划：P29～P31确认Caddy 145项vendor模块有源码归档内154份许可样本，但Go 1.26.3标准库源码不在P22候选。Go官方下载页提供的`go1.26.3.src.tar.gz`已在Git忽略目录以官方SHA-256 `1c646875d0aa8799133184ed57cf79ff24bdefe8c8820470602a9d3d6d9192b8`验证。P33拟**新建非发行候选**加入该固定源码及许可文本，不覆盖P22；仅补技术可追溯性，不推定法律放行。迁移/回滚：无运行数据迁移，弃用新候选即可回到P22；验证需整包/新增项逐件Hash、清洁解包、配置/运行布局回归，Gate维持开放。

2026-10-01/P33实施证据：新非发行ZIP 675,167,309字节、SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`，P22原21,110项Hash不变并精确新增Go源码/LICENSE两项，整包构建与独立验证PASS。清洁解包及新布局运行仍待P34；发行法律、正式License/证书与目标环境Gate保持开放。

2026-10-01/P34增量证据：P33新ZIP在全新ASCII Temp目录解包21,112载荷并全量落盘Hash/文件集回读，Go源码归档`go1.26.3`及随包LICENSE字节一致、源末次复验PASS。正式安装根/SCM/数据库未改；新布局与运行验证仍待，发行法律门禁开放。

2026-10-01/P35增量证据：新候选21,112载荷＋三清单在全新ASCII Temp安装布局映射/复制/全量Hash读回21,115目标，映射SHA-256 `d4072ed23558da5026911fad3575ee8b4d67944814b58096b6587c1bf9908580`，Go源码/LICENSE、模型指纹及包内Python/PG/Caddy和模板合成证书validate通过。新布局实际HTTPS网络、正式账户/证书与法律发行仍待；`C:\PLMTool`未建。

2026-10-01/P36增量证据：P35新布局21,115项全量Hash后，用新包内Caddy/API与合成证书实际HTTPS验证首页/两项资源、健康200、默认API404、SPA200、错误Host421，子进程/证书清理。此为默认API路由烟测，生产登录及正式信任仍待。

2026-10-01/P37增量证据：新布局全量Hash后，经新包内Caddy/PG18与临时Vault目标合成HTTPS复跑原生产登录组合，GET9/POST12、Cookie/CSRF/Host/Origin/Session/Project/Audit通过且临时源清理。API对象仍由仓库验证代码装配，非P33随包正式生产模式；目标账户/证书、SCM与法律发行Gate不因此关闭。

官方依据：[Caddy许可仓库](https://github.com/caddyserver/caddy)、[反向代理及Host处理](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)、[静态文件](https://caddyserver.com/docs/caddyfile/directives/file_server)、[SPA与API路由](https://caddyserver.com/docs/caddyfile/patterns)、[自有TLS证书](https://caddyserver.com/docs/caddyfile/directives/tls)、[Windows服务](https://caddyserver.com/docs/running)。
