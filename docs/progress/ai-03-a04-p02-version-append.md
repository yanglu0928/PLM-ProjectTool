# AI-03-A04-P02：PromptVersion 内部原子增版

版本：0.1.0；日期：2026-10-02；状态：Windows 11 隔离 PostgreSQL 18、合成内容准入内部链 PASS；正式内容准入与公开路由未完成。

输入：冻结 AI-03 DM/API-03、Schema 0059/0060、CR-AI-006、DEC-677。新增 Domain 规范化与内容指纹、内部受控增版服务、AI 自有 Repository；无生产路由、厂商外发或真实客户资料。

Changed：System/User 模板统一 NFC 和 LF；拒绝空白、越界、控制/不可见字符及明显密钥形态，SHA-256 分别计算正文哈希与包含模板/TaskType/策略引用的指纹。前置规则仅做初筛，不能证明任意自由文本安全；写入前必须通过独立内容准入端口，返回与完整规范化指纹相同的批准值，否则失败关闭。本任务只用合成准入端口验证，不提供生产适配器。

事务：当前 DeploymentAdmin/CSRF 双检查、有效 License；先为同 Key 查询不可变结果，之后根行锁校验 TaskType/非 RETIRED/强版本，分配单调 `version_no`。在一个事务中更新根乐观版本、追加 PromptVersion、写 Audit、不可变首次结果与通用收据；重放返回原版本元数据，不读取当前最高版本或激活指针。正文仅在 PromptVersion 受权表，不进入收据、结果、Audit 或普通日志。新增版本不自动激活。

Files：`apps/backend/src/plm_assistant/modules/ai/domain/prompt_version.py`、`application/append_prompt_version.py`、`infrastructure/prompt_version_repository.py`、单元及隔离验证脚本、本记录、CR/状态。

Migration：无，复用 0059/0060。API：无新增或挂载。兼容/回滚：Win11 隔离 PG18；未装配内部命令即可停止，已写版本与首次结果不可删除、后续修正通过新版本；正式账户、Windows Server 2025、Debian 13 未验。

Tests：单元 5 项通过；隔离 PG18 缺/错准入关闭、管理员/CSRF/License 拒绝、v1～v4 条件增版与历史重放、同 Key 并发、退役拒绝、Audit 故障回滚、撤权拒绝通过。后端全量 2060 项通过、3 项跳过；开发 wheel 构建通过，SHA-256 `8e6e529705a71c7049839035bf964f42fcf1e88a4836bed73c24091163680858`（包不提交）。Golden Dataset 未运行：本任务没有模型调用，不能据此判定 AI 质量。

Known Issues：合成准入不是生产证明；尚无可信审查来源来核实客户固定副本、Golden 答案或绕过 Evidence/Review 的指令。PromptRegistry/AIService、HTTP、激活、真实 Worker、质量复验、Gate3/UAT/可用包仍待。Next：`AI-03-A04-P03` 建立可信内容准入来源及受控交付，保持默认失败关闭。
