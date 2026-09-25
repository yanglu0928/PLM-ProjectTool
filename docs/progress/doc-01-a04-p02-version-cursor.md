# DOC-01-A04-P02 DocumentVersion 独立签名页游标

- 日期：2026-09-26；状态：Windows 11 游标与当前账户密钥入口 PASS，正式账户材料未供给。
- 基线：冻结 API-01 不透明分页、API-02 DocumentVersion 列表；决策 `DEC-20260926-125`。
- 实现：专用 `document-version-cursor-v1` HMAC-SHA-256 密钥；游标绑定 Session 摘要、Scope、ProjectId、父 DocumentId、page_size 与降序 `before_version_no`。不含版本正文、文件路径或客户数据；不能跨列表或密钥族使用。Windows 当前账户密钥缺失/无效时失败关闭。
- 验证：Windows 11/Python 3.13 后端 524 项无失败（2 项既有符号链接环境跳过）；5 项游标单元测试包含双 Scope 往返、篡改/跨上下文拒绝、密钥/位置校验、Windows 临时 Vault 凭据丢失及备份恢复旧游标；开发 wheel PASS。
- 无 Migration、新依赖或公开 API 变化。正式目标账户密钥须独立供给/备份，版本 HTTP GET 尚未挂载；失密不能使用 Document 列表或其他游标密钥代替。
