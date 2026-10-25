# PLT-PKG-01-A09-P26-A01：隔离布局HTTPS静态/API烟测

日期：2026-10-01；状态：`NON_RELEASE_CADDY_LAYOUT_HTTPS_PASS / AUTH_REGRESSION_OPEN`。输入P22固定ZIP、P23清洁暂存、P25隔离布局、`CR-PKG-005`。本项仅验证新布局上的包内Web边界与默认API，不把默认404当生产权限验收。

编码前检查：Phase2/Gate3开放；先对固定候选ZIP/暂存重验，再对隔离布局21,113目标的完整文件集和逐件Hash回读。任何不一致拒绝启动网络验证。只使用随机回环端口、临时合成证书和包内Caddy/API，不写正式安装根、SCM或现有数据库。

`tools/smoke_caddy_isolated_layout_https.py`固定映射SHA-256 `e30dc7732d78883c0b09be0911e0b16ade98c95b0af38008164fdc665c515ed4`，目标21,113件全量Hash通过；包内Caddy.exe/模板Hash核对，合成证书渲染后实际`caddy validate`。由该布局启动随包默认API及Caddy，HTTPS首页字节与落盘一致、两项JS/CSS资源字节一致、`/health/ready` 200/UP、默认`/api/v1/projects` 404且不被SPA改写为HTML、SPA深链200、错误Host 421。API/Caddy子进程终止，临时证书销毁；脚本exit0，定向单元1/1 PASS。

不含生产登录/Session/CSRF/审计回归，不含目标账户/客户域名证书、真实服务或数据迁移；P21认证验证基于旧P15布局，不能直接替代新布局验收。正式NOTICE/许可、Server2025、Debian13（用户暂缓实机）、安装器/升级/恢复及Gate仍开放，`release_eligible=false`。下一项P26-A02复用原生产登录断言，在新布局和包内Caddy上做隔离真实PG/Vault合成HTTPS回归；回滚弃用本非发行探针，不改变运行数据。
