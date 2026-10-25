# PLT-PKG-01-A09-P20：固定Caddy隔离HTTPS同源路由

日期：2026-10-01；状态：`SYNTHETIC_HTTPS_ROUTING_PASS / HOST_SECURITY_OPEN / NOT_RELEASE_READY`。追溯：`CR-PKG-005`、DEC-566/567、P19。只验证回环合成环境，不登记服务或更改旧P15包。

编码前检查：Phase 2/Gate 3开放；输入为固定P15 ZIP、P17隔离安装布局、P19已固定Caddy四资产和SHA/许可/SBOM。仅新增隔离HTTPS路由测试工具和定向测试，不改业务、实体、API、权限、Schema/Migration、正式配置或客户数据。验收限定为：固定字节与21,103件安装布局、合成TLS、静态index/JS/CSS、健康/API原路径、SPA深链、未知API不回退HTML；结束进程并清理合成证书。错误Host/Origin、Cookie/CSRF/SSE要实测，但不以默认健康接口替代生产安全验收。

`tools/smoke_caddy_same_origin_https.py` 验证官方Caddy EXE与输入包、旧ZIP/布局全部Hash后，在唯一临时目录生成仅2小时有效的`localhost`合成证书和Caddyfile；随包嵌入式Python仅在127.0.0.1启动默认API，Caddy在随机本机端口终止HTTPS，禁管理API及自动HTTP跳转。证书/私钥不入Git、不入包，退出后临时目录销毁。真实测试：index及两件JS/CSS与包内字节相同，`/health/ready`、`/health/live`为200/UP，默认`/api/v1/projects`为404，未知`/api/v2/synthetic`为404且不是SPA HTML，`/projects/synthetic-deep-link`回退为index。单元2/2、完整真实PoC返回`SYNTHETIC_CADDY_HTTPS_ROUTING_PASS_HOST_OPEN`；Caddy/API子进程均退出，`C:\PLMTool`不存在。

失败与安全观察保留：第一次Caddyfile把block写在同一行导致`validate`拒绝，修复后重跑。第二次代理在API ready前请求，出现502；增加API就绪门禁后重跑。随后用显式不可信Host请求首页仍返回200；尝试额外`not host`和`not header Host`匹配均未在此PoC形成可证实拒绝，已撤回未验证的规则并保留观察值`untrusted_host_status=200`。这**不是**Host安全通过，原因与生产登录策略的实际表现须在P21独立审查，不能仅依赖本站点名作结论。未测生产登录、Cookie/CSRF、SSE、正式证书/ACL、目标账户/SCM、Windows Server2025/Debian13与客户UAT。完整第三方许可仍需审查，`release_eligible=false`，Gate不变。

回滚为撤销非发行PoC工具/临时配置；历史P15/冻结API/Schema保持不变。下一项P21先查明Host校验与后端真实Origin边界，再继续同源认证及SSE，若有安全缺口按CR-PKG-005修订并复验。

后续更正（P21-A01/2026-10-01）：本项只记录了错误Host的**状态码**200，未读取正文；“静态首页返回”属于超出证据的误述。最小探针确认原Caddy配置未匹配任何站点时返回200**空正文**，没有泄露index；P21-A01新增同端口兜底站点明确返回421，并在完整随包PoC复验。保留本项原始失败记录以供追溯。
