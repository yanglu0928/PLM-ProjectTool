# PLT-PKG-01-A09-P26-A02：新布局Caddy下生产登录组合回归

日期：2026-10-01；状态：`NON_RELEASE_CADDY_LAYOUT_PRODUCTION_LOGIN_HTTPS_PASS / PACKAGED_PRODUCTION_API_OPEN`。输入P22/P23/P25/P26-A01及`CR-PKG-005`。本项复用`validation/aut-03-a07-p03-production-login/verify.py`既有真实PostgreSQL/Vault断言，通过新隔离布局内Caddy的合成HTTPS转发仓库生产API组合代码；不声称随包API正式生产二进制已作为服务运行。

编码前检查：Phase2/Gate3开放；先固定ZIP/清洁暂存/隔离布局21,113文件全量Hash及映射SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`重验，包内Caddy/模板Hash核查。只使用唯一临时PG18库/角色、Vault目标、随机回环端口及临时合成证书；不得接已有数据库、改SCM/正式安装根或使用客户证书。

将P21原测试编排的布局验证、边界资产及Caddyfile生成作参数化复用，默认旧P21行为不变；`tools/smoke_caddy_layout_production_login_https.py`注入新布局全量验真、包内`runtime/caddy/caddy.exe`及包内模板。原认证断言与新增HTTPS边界回归exit0：GET9/POST12、两次安全Cookie标记、错误首页Host421两次、错误API Host421两次、错误Origin403一次、缺CSRF403两次；真实Session/Project摘要、幂等重放/冲突及Audit原断言通过。唯一临时DB/角色和Vault目标不存在回读、PG/Caddy/API停止、临时证书及PG目录清理。定向单元1/1 PASS。

限制：本项的API应用对象由仓库验证脚本构建，并非从包内Python进程加载生产模式；包内默认API网络仅由A01验证。正式License/初始管理员/目标账户/客户证书/NOTICE、Server2025、Debian13（用户暂缓实机）、安装器、已有库迁移/恢复及Gate未验；`release_eligible=false`。下一项P27核对包内生产模式启动前置及目标账户信任材料供给/失败关闭，不能用合成结果替代真实发行仪式。回滚移除新增适配器并保持P21旧路径可用，不涉及客户数据。
