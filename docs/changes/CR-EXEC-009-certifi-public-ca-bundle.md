# CR-EXEC-009：允许 certifi 随附的公共 CA bundle

- 状态：已记录，实施中
- 日期：2026-10-27
- 关联：CR-EXEC-005/006/007/008、PR #55、PLT-PKG-01-A09-P51-A17
- 范围：仅 Windows embedded backend 候选包中的 certifi 公共根证书文件。

## 证据

Hosted Windows run `40454022815` 成功完成后端测试、前端测试、Python 3.13.15 基础 runtime 重建和 PG18/pgvector 重建。embedded 依赖解析及安装成功，安全扫描拒绝文件 `packages/certifi/cacert.pem`，且未上传候选包。该路径属于 certifi 提供的 TLS CA bundle；当前扫描器以 `.pem` 扩展名整体拒绝，没有区分公开证书与私钥。

## 决策与差异

安全规则仍禁止所有默认 PEM 文件。仅对相对路径精确等于 `packages/certifi/cacert.pem` 的文件给予例外，并在纳入前读取内容，要求至少包含 PEM CERTIFICATE 块且不得包含任何 PRIVATE KEY 块。该文件仍进入逐文件 SHA-256 manifest。其他目录中的 PEM、环境文件、日志、密钥和证书容器继续拒绝。

## 风险、迁移与回滚

- 证书 bundle 内容可能随 certifi 版本变化；固定路径例外必须同时满足内容格式校验，并把文件哈希写入候选 manifest。
- 此例外不会安装私有证书，也不证明目标环境 TLS/代理策略已验证。
- 校验不通过或出现其他敏感类型时停止上传。回滚方式是删除例外并恢复整体 PEM 拒绝。
- 不更改产品架构、API、Schema、依赖要求或发布边界，不代表 Pilot/正式发行验收通过。

## 验证计划

在 hosted Windows runner 重跑全量相关检查。确保仅精确 certifi 路径且内容只含公开 PEM certificate 的文件可通过；其他 `.pem` 或含私钥内容继续失败；embedded clean-path 导入、runtime 逐文件 hash readback 和上传门禁全部通过，失败时不产物。该检查不代表 TLS 连通性或生产服务账户信任策略验收通过。
