# AI-03-A07-P03：可选 Prompt LIST/GET HTTP

日期：2026-10-02；版本：0.1.0.dev0。Changed：新增可选 `AI_PROMPT_LIST/GET` Router，按冻结路径实现管理员 Session/可信 Host/License、签名游标分页、安全元数据和详情强 ETag；默认应用不挂载。DRAFT/RETIRED 的历史指针不投影成活动版本，不返回正文。Files：`modules/ai/api/prompt_metadata.py`、`entrypoints/api.py`、合同测试、隔离验证脚本及运行时合同补充。

Migration/Architecture/依赖：无变化；不改冻结 `/api/v1`。升级/回滚：显式注入 Router 才可访问，撤注入恢复404，数据库不变。Tests：合同3项覆盖默认关闭、成功/分页/校验/错误映射、权限/Session/License及坏投影；Win11隔离PG18实际ASGI两页/ETag、DRAFT/ACTIVE/RETIRED、正文不泄露、无权/许可/游标/撤销会话拒绝 PASS；后端2097运行/3跳过 PASS；开发wheel SHA-256 `4865b13026d5e820ee6aebddcc64a270a3f039509dd842baedeadbd14b532b7a`，非交付包。

Known Issues：Windows专属游标密钥及平台组合、正式目标账户/发行信任、Server2025/Debian、Invocation资格、Gate3/UAT/可用包未完成。Next：`AI-03-A07-P04` 专属密钥来源及 Windows 显式组合验证。
