# DOC-03-A04-A02 受权 UploadIntent 创建与短时 Token

日期：2026-09-25；范围：Phase 2 / Document 内部创建入口。追溯：冻结 API-02 `DOCUMENT_UPLOAD_CREATE`、CR-DOC-004、Migration `20260925_0023`、DEC-20260925-101。

## 实施

- 新建/既有 Document 的意图字段、Scope/Project、用途、大小/MIME 提示做输入校验；上传 `GENERATED_ARTIFACT` 拒绝。实际 Content 的字节、文件签名和 MIME 仍须在下一项重新验证，hint 不构成可信事实。
- 注入授权 Port，在同一数据库事务内做权限检查、Project ACTIVE/目标 Document 归属和状态检查，创建 Intent、审计和幂等收据。同 Key 重放仅重新派生原 Token，未过期的 CREATED/CONTENT_READY 可重放；终止/过期拒绝。
- Token 使用独立稳定 256-bit Key 的域分离 HMAC，绑定 upload_id、actor_id、scope/project；数据库只存 SHA-256 摘要。过期时间与状态存于不可变身份的 UploadIntent 数据库行，后续 Content 必须同时验证当前 Session、创建者、Token 摘要、范围和数据库时效。生产 Key 来源未接线，默认/生产应用均不开放本入口。

## 验证

- Windows 11 / Python 3.13：后端 464 项无失败，2 项符号链接场景因当前账户权限跳过；新 Token/校验单元测试 2 项通过。
- PostgreSQL 18 临时独立库：新建、并发同 Key 重放、数据库摘要、单次 Audit/收据、异载荷冲突、拒权、跨项目 Document、既有 Document、审计失败全事务回滚、终止后重放拒绝及密钥缺失拒绝通过。验证只用合成账号和合成 Key；临时库已删除，数据库服务已停止。
- 后端开发 wheel 构建通过。无新增 Migration、公开 API 或生产依赖。

## 遗留

正式 Session/License/CSRF/Project Role 授权 Port、目标账户独立密钥供给与轮换恢复、HTTP 创建、流式 Content/Commit/Abort、Parser Job/Outbox 均未接线。密钥轮换须等旧 Intent 过期或保留旧密钥；失密会使旧 Intent 失败关闭并要求重新创建。Server 2025、Debian 13 和最终发行未验证。下一项 DOC-03-A04-A03 流式 Content 受控暂存与校验前置。
