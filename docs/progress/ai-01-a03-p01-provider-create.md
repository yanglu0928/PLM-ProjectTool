# AI-01-A03-P01：内部受权 Provider 创建

日期：2026-10-02；结果：`INTERNAL_CREATE_PASS / PUBLIC_API_CLOSED`。AI-01-A03 依 DEC-20261002-624 拆为创建 P01 和配置追加 P02，本文件只覆盖 P01；CR-SEQ-001 的前置执行不关闭 Phase 2/Gate 3。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 仍开放；独立前置 `AI-01-A03-P01`|
|输入基线|ADR-004、冻结 DM-04/SC-01/02/API-03、AI-01-A01 形状、A02 迁移0054；原 Gate 2 内容不追写|
|前置任务|A01/A02 已验证；现有 Auth 当前 Session/CSRF/DeploymentAdmin、License Guard、Platform SecretRecord、持久收据与 Audit Port 可复用|
|涉及模块/实体|AI Application 创建编排、AI 自有 Repository、Platform 自有 Secret 元数据证明；`AIProvider`/配置版本、已有收据与 Audit|
|涉及 API|无公开 HTTP 变更；冻结 POST 仍待单独路由/装配验收|
|涉及权限|当前有效 DeploymentAdmin Session + CSRF，两次验证；License 当前有效；首次创建同事务锁定 ACTIVE/AI_PROVIDER_KEY/AI_PROVIDER_ADAPTER/有效 SecretVersion；同 Key 历史重放仍重验管理员和 License|
|验收|真实 PG18 创建仅 CONFIGURED；持久同 Key 并发只一条根/版本/成功 Audit/收据；异载荷冲突、权限/许可/Secret 拒绝与 Audit 故障原子回滚；后端回归和 wheel|
|风险|误把“配置成功”当 Provider 激活/连接或客户数据外发；本路径无厂商调用、无 Secret 解密，后续调用仍必须重验当前 Secret 和逐次外发授权|

## 结果

Application 仅接收冻结非敏感元数据及 SecretRef UUID；Platform 自有适配器在同一事务锁定 SecretRecord 并核对当前有效版本，AI Repository 原子插入部署级根与不可变首版。持久收据只存指纹/标识，不存 Key 明文或正文；重放时当前管理员和 License 重新证明，已停用 Secret 只允许返回已成功的历史身份，不代表可再次使用。成功 Audit 与业务及收据同事务。

定向单元2项 PASS；Windows 11 隔离 PostgreSQL18.6 真实 Auth Session/CSRF、合成 License Guard、Secret 元数据、幂等并发、Audit 回滚、Secret 停用后历史重放及角色撤销拒绝 PASS。后端全量1909运行/3跳过、0失败；开发 wheel SHA-256 `e00d6490aa2d49ceac368892e843f4809e1e97ec7cd461d65e5f810dac956acd`。测试临时库已清理，原本停机的 PG 实例正常停回；无生产数据库、Schema、API/依赖变化和外部网络调用。

未完成：配置追加 P02、公开 Provider CRUD、真实 License 信任材料/Secret 主钥装配、Provider Test/Activate、ModelRouter、外发审批、POC-03 质量、正式三平台/UAT/发行。合成 Guard 证明端口调用与失败关闭，不是正式 License 验收。下一项 `AI-01-A03-P02` 实现 CONFIGURED/SUSPENDED Provider 的配置版本追加、强预期版本、同事务 Secret/Audit/收据和历史重放；ACTIVE 必须先受权暂停，不原地切换活动配置。
