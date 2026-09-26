# 既有项目内部初始化隔离验证

`verify.py` 在 Windows 11/Python 3.13/本地 PostgreSQL 18.6（55432，poc_admin 测试环境）执行，创建并 finally 删除随机 `wflpm_*` 临时库。需预先配置后端 src/项目数据库依赖搜索路径；不连接生产。

证据为真实数据库中的 Session/CSRF/项目角色/归档与撤销事实。License 是合成 Guard，不能证明真实发行 License 信任源。覆盖四类非 PM/跨项目/全局管理员拒绝、过期 License、重试并发、Audit 回滚，全部结构保持 NOT_STARTED/PENDING。

2026-09-26 实测 PASS；后端 630 项无失败（2 项环境跳过）。不是 HTTP、CLI、业务 Gate 或生产回填验收。
