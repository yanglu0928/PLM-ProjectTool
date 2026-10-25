# SOL-03-A04-P03-P03-P06-A03-P05-A05：项目 GLOBAL 候选 Windows 显式平台组合

日期：2026-10-09。结果：Windows 11 隔离 PostgreSQL 18.6/真实 ASGI 合成链及后端回归通过；正式目标服务账户、Windows Server 2025、浏览器及发行仍未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate 2 API-04、CR-SOL-018、DEC-1156、已验 A02～A04 Catalog/Owner/HTTP。
- 单一问题：在 Windows 显式只读/读写平台模式安全装配项目 GLOBAL 候选 GET，并提供独立、可恢复的当前账户 Vault 游标密钥。
- 模块/实体/API/权限：Windows 生产组合及密钥解析；复用既有 Document/Parse/Evidence 物理来源、项目读授权和 License；不改 ORM/Migration、旧 API、角色或依赖。
- 验收：默认登录不开放；两种显式平台模式挂载；缺密钥或安全依赖拒启动且释放资源；独立密钥与备份恢复；Win11 真实合成 ASGI/PG 完整项目候选链；后端全量回归。
- 风险：正式游标密钥误复用、假物理证明、部分路由先公开、旧游标恢复失败。以专用 KeyRef、受控根组合、启动原子失败和 Vault 备份恢复定向测试控制。

## 实施与验证

新增 `project-global-reference-candidate-list-cursor-v1` 专用当前账户密钥引用；仅 Windows `--platform` 和 `--platform-write` 显式模式从 SecretKeyProvider 解析并装配项目候选路由。工厂以受控本地根构建 Document/Parse/Evidence 当前证明、发布 Catalog、PM/IM 项目授权与 Owner；默认登录仍为 404。密钥或任一安全端口缺失则在路由发布前拒启动并释放运行资源，不生成进程临时正式密钥。

独立密钥/工厂定向测试 16 通过、84 子例；启动模式定向 40 通过、17 子例，覆盖默认 404、显式平台未认证 401、密钥缺失的两模式失败关闭及资源释放。真实 Win11 隔离 PG18.6、合成文档/证据来源、当前项目成员与 License/Session 的 Windows 工厂/ASGI 脚本退出 0，复用 A04 HTTP 断言。后端全量 3496 通过、3 跳过、5398 子例通过。本轮未用正式服务账户/Vault/CA，也没有据此宣称生产部署通过。

兼容/升级：无 Schema/Migration、旧 `/api/v1`、角色或依赖变化。启用显式平台模式前，需在目标服务账户的 Windows SecretKeyProvider 安全供给独立 32 字节密钥并备份；缺钥即拒启动，不降级为不签名游标。回滚可移除可选路由装配或切回既有程序版本；发布事件、审计及收据历史保留。Server 2025、正式账户密钥/ACL/CA 与 SCM 安装恢复、前端真实浏览器、20 并发、Gate 3/发行未验；Debian 13 实机依用户指令跳过。

TraceLink：Gate 2 API-04 → CR-SOL-018 → DEC-1152～1156 → 0158/发布 → A02 Catalog → A03 Owner/游标 → A04 HTTP → 本 Windows 组合 → A06 前端/浏览器。
