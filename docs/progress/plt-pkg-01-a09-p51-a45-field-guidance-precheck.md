# PLT-PKG-01-A09-P51-A45：报告逐字段填写指引（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成；尚未改程序。

## 任务定位

Phase 2 Platform Core；Gate 3、Pilot、Formal Release 均未通过。A44 已把非秘密登记器和只读报告纳入父包。报告正确返回缺项键名，但用户需再对照 README 理解每个字段，诊断输出本身尚未说明字段需要维护什么及参考来源。

## 单一目标

扩展 A44 readiness JSON，在 `input_register_missing_fields` 之外为每个缺项返回固定的人类可读提示：需登记的非秘密值/引用类型、推荐证据来源，以及不可输入的秘密类型。提示只基于静态字段定义；永不拼入用户提供值、路径、密钥或客户资料。Complete register 的报告仍必须 `pilot_ready=false`、`launch_authorized=false` 且要求独立核验。

## 输入/输出与安全边界

- 输入登记结构沿用 V1；不更改 JSON schema、业务/API/DB、License或服务启动门禁。
- 指引覆盖产品公钥摘要、License证据引用、固定数据库Credential Manager目标、服务身份引用、TLS证书Thumbprint/DNS名，以及4种EVD证据引用。
- `database_credential_target` 是固定目标，不是凭据值；说明不得收集或显示密码、数据库连接串、私钥、API Key、License正文、证书私钥或客户材料。
- Invalid JSON/未知字段仍只输出固定错误；不得从不可信输入形成动态字段说明或回显内容。

## 验收标准

- 缺项登记会为每个缺失键返回且仅返回对应固定指引；所有9个非固定字段均有指引。
- 完整合成登记 `input_register_guidance` 为空，但 `COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION`、`pilot_ready=false`、`launch_authorized=false` 保持。
- 注入字段值/未知值不得出现在报告、stderr或错误摘要；服务/API/DB/监听器不启动；包 manifest/checksum不变。
- 单测、父包真实 PowerShell 报告 smoke 与 A17/A34/PG组合仅在 GitHub hosted Windows Server 2025 D盘临时环境验收；不在用户本机运行，不推定 Windows 11新运行兼容。

## 兼容/风险/回滚

这是现有诊断响应的向后兼容增量JSON字段；既有字段与CLI exit code不变。消费者若拒绝未知字段，应以现有非发行工具的独立版本更新处理；没有API Contract改变。回滚为恢复旧报告输出和相应测试，候选由新run重建。无数据迁移或外部网络请求。

## 编码前检查结论

本WBS仅解决报告缺项之后的即时可操作性，不将指引当作已验证事实，也不将登记完整当成授权。复用A44已验证的只读包边界与合成输入；先提交本检查，随后方可编码。更新结果必须在STATUS、CHANGELOG、CR-PKG-012/CR-EXEC-005并保留历史失败/修复记录。