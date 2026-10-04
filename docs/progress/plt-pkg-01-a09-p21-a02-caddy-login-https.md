# PLT-PKG-01-A09-P21-A02：Caddy HTTPS 真实生产登录链

日期：2026-10-01；状态：`SYNTHETIC_CADDY_PRODUCTION_LOGIN_HTTPS_PASS / RELEASE_OPEN`。追溯：`CR-PKG-005`、P21-A01、冻结Auth合同与AUT-03-A07-P03。非发行合成验收，旧P15 ZIP不改。

编码前检查：Phase2/Gate3开放；输入为固定P15 ZIP/P17布局、Caddy v2.11.4输入、P21-A01 Host兜底、原`validation/aut-03-a07-p03-production-login/verify.py`真实PG/Vault断言。只增隔离HTTPS验证脚本，不改业务代码、实体、API、权限、Schema/Migration或正式配置。验收：全量Hash、唯一临时PG18、真实生产登录组合根、Caddy HTTPS同源Host/Origin/Cookie/CSRF/Session/Audit及清理；风险为合成证书、当前Windows账户Vault和回环进程不等于正式目标服务账户/证书/Server2025。

新增`tools/smoke_caddy_production_login_https.py`，先核固定Caddy官方资产与P15安装布局21,103件Hash，再在唯一临时目录启动PG18.6、按原验收脚本创建唯一角色/库并迁移至head、唯一Windows Vault目标。以固定Caddy合成`localhost`证书和127.0.0.1 Uvicorn替换原`TestClient`传输层，原脚本的真实scrypt登录、错误密码/Origin、项目摘要、Session读/续期/注销、旧Cookie拒绝、幂等重放/并发、冲突与DB Audit断言均重新运行，**不是仅mock业务层**。额外验证错误Host首页及登录POST各两次421、错误Origin403、两次HTTPS登录Cookie`Secure`/`HttpOnly`/`SameSite=lax`、两次缺CSRF续期403且无Set-Cookie。网络计数：GET9、POST12（不含额外安全探针）；隔离完整脚本exit0。

原脚本退出后，在临时PG内回读合成数据库与角色均不存在；Win32 Credential Manager `CredReadW`确认唯一临时Vault目标不存在且错误1168。随后停PG18并确认无存活实例，删唯一临时集群；Caddy与API子进程退出、合成TLS目录清除、`C:\PLMTool`仍不存在。没有使用真实客户凭据、License私钥或已有数据库。首次链已通过，增加缺CSRF与资源清理回读后完整重跑再次通过。

结果只证明**Windows11当前账户+合成信任源/证书+回环端口**的生产登录链，不能声称客户证书/目标账户ACL/正式License、三平台安装、SSE、完整业务UAT、NOTICE或Gate通过。`release_eligible=false`。下一项P21-A03验证SSE经Caddy转发与断线清理；其后继续新候选装配、安装/升级与发行门禁。回滚撤销此验证脚本，不触碰原ZIP、客户数据或冻结API/Schema。
