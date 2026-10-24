# AI-03-A06-P05：Prompt 退役平台装配前置核查

版本：0.1.0.dev0；日期：2026-10-02；状态：装配边界核查 PASS；实际 Windows 组合/正式目标账户未验，无程序变更。

依据：冻结 `AI_PROMPT_RETIRE`、CR-AI-007/009、A06-P04隔离HTTP结果。CR-AI-007 的独立 Prompt 签名清单用于防止未审正文新增或激活；退役仅将既有模板从 DRAFT/ACTIVE 单向置 RETIRED，不引入新正文或可调用版本，故不应强制以 Prompt 清单为前置。它仍需现有平台受信 License、当前管理员Session/CSRF、真实目标账户与受控Schema0062。

只读证据：`production_login.py` 当前在 Windows 显式平台写模式装配 AIModel 状态等受控命令，但没有调用 `create_ai_prompt_retire_router`；`create_app` 仅提供可选注入点。包内 Prompt 公钥/签名清单均不存在，增版/激活继续保持关闭。P04默认应用404和隔离PG18可选路由已通过；这不能证明正式平台组合或发行信任。

Changed：仅明确安全边界/下一任务；不生成测试密钥、不启用入口、不修改生产数据库。Migration/API/依赖：无。Tests：只读源代码/信任文件核查，未执行本项新运行测试。兼容/回滚：无行为变化。Known Issues：Windows目标账户/正式License信任和Prompt内容准入材料、Server2025/Debian、Invocation资格/Gate3/UAT/可用包仍未验。Next：`AI-03-A06-P06` 将退役仅装入 Windows 显式写组合并做隔离PG18/合成平台信任端到端；默认/只读组合仍关闭。
