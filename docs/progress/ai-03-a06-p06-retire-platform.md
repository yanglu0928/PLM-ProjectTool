# AI-03-A06-P06：Windows 显式写组合接入 Prompt 退役

日期：2026-10-02；版本：0.1.0.dev0；依据 CR-AI-009、DEC-693、冻结 `AI_PROMPT_RETIRE`。

## 变更与边界

仅在 Windows `--platform-write` 显式写组合装配退役 Router，复用平台运行时 UOW、License guard、Session/Origin/CSRF、幂等收据与 Audit。默认登录/只读组合仍为 404。退役是单向禁用，不创建或激活 Prompt 正文，故不要求 Prompt 内容签名清单；增版/激活仍保持关闭。目标账户与正式发行信任不能由合成测试代替。

复用 Schema0062，不新增 ORM/Migration、依赖或冻结 API Breaking Change。升级前需受控应用0062并满足平台发行信任；回滚可撤销路由装配使接口恢复404，但历史退役/Audit/收据须保留，非空0062不得物理降级。

## 验证

- Win11 隔离 PostgreSQL 18、合成平台身份/License：登录/只读 404、显式写 200及原Key重放、普通用户404、License403、缺平台游标密钥启动失败；SQL仅一处根状态变更、一份Audit/首次结果/收据，验证脚本 `validation/ai-03-a06-p06-retire-platform/verify.py` PASS。
- 后端全量：2090运行、3跳过，PASS。开发 wheel 构建 PASS，SHA-256 `caa0d4fb1951618c2ad7c0ba66158e166d5194dfeb4cc9ee414c62bcb96d2703`。wheel仅作开发验证，非可交付包。

## 未完成

正式目标账户/License/密钥与发行信任、生产迁移、AI Invocation 对 RETIRED 的独立拒绝、Windows Server 2025/Debian 13、Gate 3/UAT 和可用程序包均未验收。不得据此宣称生产可用。
