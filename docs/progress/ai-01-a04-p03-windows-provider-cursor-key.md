# AI-01-A04-P03：Windows Provider 游标密钥只读来源

日期：2026-10-02；结果：`WINDOWS_CURRENT_ACCOUNT_SYNTHETIC_PASS / FORMAL_KEY_OPEN`。输入 P02 独立签名游标与已有 Windows 当前账户 Credential Manager 生命周期；本任务不供给正式密钥或关闭 Phase 2/Gate 3。

## 编码前检查

|项目|结论|
|---|---|
|当前 Phase/WBS|Phase 2 开放；`AI-01-A04-P03` Windows 专用游标钥来源|
|输入基线|冻结 Provider LIST/安全约束，P02 专用 HMAC 游标，现有 Windows Vault 只读/备份恢复机制|
|前置任务|P02 游标编码与隔离 PG 分页已验证；Windows Credential Manager 现有 Provider 可复用|
|涉及模块/实体|仅入口组合适配器和测试；无实体/Schema 变化|
|涉及 API|无公开 API 变化；列表 HTTP/生产挂载仍待|
|涉及权限|仅当前进程账户 Vault 的固定 `ai-provider-list-cursor-v1`；无 Key/错长/异常失败关闭，不自动生成正式密钥|
|验收|KeyRef 专用性、32字节检查；唯一随机测试引用加密备份、删除 Vault 凭据、恢复后旧游标可解码，清理临时引用|
|风险|合成当前账户恢复不等于目标服务账户/Server 2025/Debian 生产密钥供给|

## 结果与验证

新增 `create_windows_ai_provider_list_cursor_codec`，只从当前账户 Windows Vault 读取固定专用 KeyRef，不复用 Secret、Project 或其他资源游标签名钥；缺失、错长或解析异常均失败关闭。单元用 FakeResolver 验证 KeyRef/错误；Windows 11 本机仅创建随机测试引用和临时加密备份，删除临时凭据后证明原游标失效，恢复备份后旧游标再次解码，最后清理测试凭据。未读取/写入正式 KeyRef。

定向2/2 PASS（含 Windows Vault 实测）；后端全量1917运行/3跳过、0失败；开发 wheel SHA-256 `25c8d9aae006f9bbab700500f116591ab168103b3dca30279889057778672bc3`。无 PG 测试需要，无外部 AI 调用或客户资料外发。

兼容/升级：无 Schema、公开 API 或依赖变化；不装配入口即可代码回退。正式目标账户 KeyRef、独立备份和恢复演练未完成；Server 2025/Debian 目标来源、Provider HTTP/装配、正式信任/激活/外发、质量/Gate/UAT/可用包仍未验。下一项 `AI-01-A04-P04` 可选 Provider GET/LIST HTTP 合同与隔离 PG 验证，不在默认组合自动开放。
