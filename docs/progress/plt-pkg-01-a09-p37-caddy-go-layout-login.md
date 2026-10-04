# PLT-PKG-01-A09-P37：新布局Caddy下生产登录组合回归

日期：2026-10-01；状态：`NON_RELEASE_CADDY_GO_LAYOUT_PRODUCTION_LOGIN_HTTPS_PASS / PACKAGED_PRODUCTION_API_OPEN`。输入P33固定候选、P34暂存和P35新布局，复用`validation/aut-03-a07-p03-production-login/verify.py`既有真实PostgreSQL/Vault断言；API应用对象仍由仓库验证脚本构建，不冒充随包生产模式进程。

编码前检查：Phase2/Gate3开放；先核P33/P22谱系、暂存与新布局21,115件全量文件集/Hash，使用新包内Caddy与PG18、唯一临时PG库/角色与Vault目标、随机回环端口/临时合成证书。无正式账户/客户证书或已有数据库连接，不改实体/API合同/Schema/SCM/正式根。验收为原登录/Session/审计断言与HTTPS Host/Origin/Cookie/CSRF边界全通过，临时来源清理回读。

`tools/smoke_caddy_go_layout_production_login_https.py`真实运行exit0：GET9/POST12，两次安全Cookie标记、错首页Host421两次、错API Host421两次、错Origin403一次、缺CSRF403两次；原真实PG/Vault登录、Session读取/续期/注销、精确重放/冲突、Project摘要及Audit断言PASS。布局映射SHA-256 `d4072ed23558da5026911fad3575ee8b4d67944814b58096b6587c1bf9908580`与21,115件Hash再验；唯一临时DB/角色和Vault目标不存在回读，PG/Caddy/API停止、临时证书与数据目录清理。新旧适配器定向单元2/2。首次旧适配器单测因默认参数提前捕获验证函数而失败；改为调用时解析后新旧测试均PASS，完整真实流程随后通过。

限制：随包默认API已在P36运行，但本项的生产登录API应用对象由仓库代码装配，**未**从P33包内Python以正式`--platform-write`模式及正式信任源启动；真实产品SSE、目标账户证书、SCM/安装/升级/Server2025/Debian13（实机暂缓）、NOTICE法律与Gate未验，`release_eligible=false`。下一项P38应转正式Windows安装与账户/证书/信任源的可执行前置设计和独立验证，不重复把合成认证当正式生产PASS。回滚禁用新非发行探针，原P26证据和客户数据不变。
