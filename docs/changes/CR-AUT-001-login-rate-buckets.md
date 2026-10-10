# CR-AUT-001：持久登录限流表补充

日期：2026-09-25；状态：IMPLEMENTED / AUT-03-A02 PASS（公开登录与清理调度未完成）。

来源：冻结 API-02 要求 AUTH_LOGIN 限流，原 Gate 2 Schema V1 未列登录尝试计数表。进程内缓存无法覆盖多个 API 进程或重启，不能单独作为发行验收依据。冻结技术栈允许 PostgreSQL；不引入 Redis 等新组件。

方案比较：A 在进程内计数，简单但跨进程可绕过；B 在 PostgreSQL 新增仅 Auth 内部可见的窗口桶，以原子 UPSERT 预约尝试。选择 B。PostgreSQL 18 官方 [INSERT 文档](https://www.postgresql.org/docs/18/sql-insert.html) 说明 `ON CONFLICT DO UPDATE` 的原子性；OWASP [Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html) 将登录节流列为防护手段。限值为部署内初始策略，须经实际压力/误拒评审。

差异：在冻结 DB Schema V1 之外增加 `plm.auth_login_rate_buckets`；只保存来源/账户摘要键、窗口时间和尝试计数，不保存原始 IP、用户名、密码、Token 或响应。API 路径、DTO、架构与产品 Scope 不变，原冻结提交仍保留。

验证：Windows 11/Python 3.13 后端 215/215、限流服务覆盖率 96%、PostgreSQL 18.6 空库 up/down/re-up、已有用户升级、ORM drift=0、约束、40 并发限 30、账户限 10、窗口重置、非空降级拒绝与维护后回退、wheel 构建 PASS。下线/降级前须确认桶数据可清理；这些桶是短期安全运行状态，不是用户或审计历史。保留一天后受控清理的调度与反向代理可信客户端地址另在 AUT-03 后续任务验收；未完成前不可宣称公开登录生产可用。
