# AI-01-A04-P02：Provider 内部有界列表与签名游标

日期：2026-10-02；结果：`INTERNAL_LIST_PASS / HTTP_AND_PRODUCTION_KEY_OPEN`。依据冻结 API-01/API-03、DM-04、0054 与 P01 安全投影；CR-SEQ-001 允许此前置任务，不关闭 Phase 2/Gate 3。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 开放；`AI-01-A04-P02` 内部列表|
|输入基线|冻结 Provider LIST、统一分页游标、安全脱敏与管理员权限，A03/P01 已验|
|前置任务|Provider 当前配置根/版本、只读管理员 Session、License Guard 和安全详情投影已具备|
|涉及模块/实体|AI Application 签名游标/受权读取、AI Repository keyset；Provider 当前配置|
|涉及 API|本项无 HTTP；冻结 GET LIST 将独立装配|
|涉及权限|每页先验当前 DeploymentAdmin，再验证 License，再在读取事务内重验管理员；游标绑定 Session/页长/资源家族|
|验收|最大200条；不可变 `(created_at, provider_id)` 降序 keyset；SecretRef 只以掩码返回；篡改/错钥/错会话/错页长拒绝、跨页不重复；失效许可/撤权拒绝|
|风险|复用其他资源游标密钥或把合成测试钥当正式供给；使用专用密钥类型，正式目标账户 Vault/恢复单独验收|

## 结果与验证

列表 Service 接收专用 32 字节游标签名器，不存在签名器即失败关闭；Repository 仅显式选择 Provider 根及当前配置的元数据列，不 JOIN Secret 密文表。内部页长为1～200，仓储最多查询201行；签名游标绑定家族、DeploymentAdmin 范围、当前 Session 摘要、页长及稳定 keyset 位置。每页重验当前权限和 License，不把旧游标当长期授权。配置版本变化只改变当前安全投影，不改变根的分页位置。

Windows 11 隔离 PostgreSQL18.6：3条 Provider、其中1条配置升版、2+1 跨页、游标后插入新首条不混入旧后续页、SecretRef 不回显、错页长/篡改/普通角色/失效License/撤权拒绝 PASS。游标签名单元覆盖错钥、错会话、错页长与篡改；定向单元4项，后端全量1915运行/3跳过、0失败。开发 wheel SHA-256 `0a3f9c771b0ec8a07979b1416a7b33d7a56756f9e94f106d557d86a0fda478a0`。隔离测试库删除，PG 恢复原停机状态。无外部 AI 调用和客户数据外发。

兼容/升级：无 Schema、依赖或公开 API 变化；需已有0054。不装配内部列表即可代码回退，Provider 历史不改。未完成：正式目标账户独立游标密钥与备份恢复、Provider GET/LIST HTTP、正式信任/主钥、激活/路由/逐次外发、质量、三平台、Gate/UAT/可用包。下一项 `AI-01-A04-P03` 完成 Windows 当前账户独立 Provider 游标密钥只读来源及测试引用恢复；不能将合成钥提升为正式密钥。
