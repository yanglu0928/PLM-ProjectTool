# PLT-02-A07-P04-A02：Secret 元数据列表安全游标

- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P04-A02。输入：Gate 2 冻结 API-01/API-02、PLT-02-A03 元数据投影、P04-A01 可选详情 HTTP。前置满足可选列表开发；正式签名密钥供给和生产装配仍未完成。
- Changed：新增可选 `GET /api/v1/admin/secrets`，默认 50、最大 200，固定 `created_at DESC, secret_id DESC`；HMAC-SHA256 游标绑定资源族、DeploymentAdmin Scope、Session 摘要、分页参数指纹及最后排序键。伪造/换会话/换页大小均拒绝，不降级为首页。请求仍经可信 Host/Origin、Session、内部管理员和 License 保护；输出仅元数据。
- Files：Platform 游标编码器、列表 API/应用工厂、内部 HTTP 专用 keyset 查询、单元/契约测试、临时 PostgreSQL 验证、决策/版本/状态记录。
- Migration：无；不更改 Schema 或现有内部 UUID 分页语义。
- API：冻结 `PLATFORM_SECRET_LIST` 只读路径；默认应用不注入仍 404。创建/轮换/停用仍未公开。
- Tests：Windows 11/Python 3.13 后端 355/355 PASS；合成 HTTP 分页/安全投影/游标拒绝/权限失败关闭；PostgreSQL 18 临时库同时间戳 ID 倒序 keyset、活动/停用锁版本与许可拒绝 PASS；开发 wheel PASS。临时库已删除，数据库服务已停止。
- Result：本项可选 API 和真实 SQL 分页验证 PASS；生产密钥来源和管理路由装配未验收，不等于 A07 或 Gate 3 PASS。
- Known Issues：游标签名密钥仅有显式依赖注入边界，尚无目标账户受保护来源/恢复演练；正式 License 公钥/可信时间密钥、Server 2025/异账户和 Debian 13 未验证。PostgreSQL 的 Secret 创建时间不可事后修改；测试改为同一插入语句构造相同时间戳，未改 Schema。
- Next：PLT-02-A07-P04-A03 Windows 游标签名密钥当前账户 Vault 来源及恢复；随后生产只读路由安全装配与写接口前置核查。
