# AI-03-A06-P04：PromptTemplate 可选退役 HTTP

版本：0.1.0.dev0；日期：2026-10-02；状态：Win11 合成合同及隔离 PG18 HTTP 链 PASS；生产挂载仍关闭。

输入：冻结 API-03 `AI_PROMPT_RETIRE`、CR-AI-009、Schema0062、内部退役服务、DEC-692。Changed：可选Router验证受信Origin、Session/CSRF、幂等键、强If-Match、严格空JSON；响应二次核对Template/预期锁版本，只投影首次RETIRED/ETag，不暴露旧活动指针或Prompt正文。默认App不挂载，生产组合未变。

Files：`modules/ai/api/retire_prompt_template.py`、`entrypoints/api.py`、合同测试、隔离PG18 HTTP脚本、API补充/决策/状态/版本说明。Migration：无，复用0062。API：冻结路径与200/错误码不变，新增可选实现而非生产启用。

Verification：合同3项覆盖默认404、200/重放快照、请求畸形/权限/版本/许可/冲突映射；Win11随机隔离PG18实际HTTP→Session→服务→事务，默认/普通用户/未知模板404、200及重放、409、许可403，SQL单次RETIRED根状态/Audit/结果/收据，随机库清理。后端全量2090运行、3项既有跳过；开发wheel SHA-256 `92b65e4fc58a0ba583f4c7eeb99e3bb289daee47d8c709efeb38fae3012c05a5`（临时输出未提交）。

兼容/升级/回滚：无新依赖/Schema/Breaking API；只有显式注入Router后才可用，撤注入恢复404，历史状态/结果/Audit/收据保留。Known Issues：正式Prompt审查/发行信任、目标账户/Server2025/Debian、退役后Invocation资格、Gate3/UAT/可用包均未验。Next：`AI-03-A06-P05` 生产挂载前置核查；不满足则转向Prompt只读/Invocation资格等独立任务。
