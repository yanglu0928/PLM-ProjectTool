# AI-03-A05-P03：PromptVersion 内部受控激活

版本：0.1.0.dev0；日期：2026-10-02；状态：Windows 11 隔离 PostgreSQL 18 合成准入内部链 PASS；生产激活入口未开放。

输入：冻结 AI-03 API/DM、CR-AI-007/008、Schema0061、已记录的激活历史版本当前准入要求。本项只实现内部命令和 AI 所有仓储，不新增公开 API、Schema、依赖或外发。

Changed：DeploymentAdmin 当前 Session/CSRF 与 License 双重检查；仅 DRAFT/ACTIVE 根可激活同模板已有不可变版本。目标版本正文、Hash、策略引用重新规范化并计算完整指纹，必须得到当前准入端口精确批准；未列版本失败关闭。根行锁和强版本控制切换活动版本，同事务写 Audit、不可变首次结果与幂等收据。原 Key 重放再次验证当前授权/许可，只返回首次结果，不读取当前活动根；新 Key 同版本重复激活拒绝。RETIRED 不可新激活。

Trace：`application/activate_prompt_version.py`、`infrastructure/prompt_activation_repository.py`、`validation/ai-03-a05-p03-activation/verify.py` → CR-AI-008 → DEC-687 → Gate2 原冻结 API-03；不追写原冻结提交。

Migration：复用0061，正式生产尚未迁移。兼容/升级：先按0061受控迁移并备份，再取得真实审查/签名清单及目标账户可信装配；本项未挂生产入口。回滚：关闭未挂服务即可停止新激活；已存在的根状态和不可变结果/Audit/收据不得删除，需向前修复或受控恢复。

Verification：Win11 隔离 PG18 随机库合成准入脚本 exit0，覆盖管理员/CSRF/License、未列/不存在版本、初激活与切换、并发冲突、跨状态历史重放、Audit 故障回滚、退役与撤权；随机库已清理。后端全量2082项通过、3项既有跳过；开发 wheel 构建通过，SHA-256 `c6da186d29d660b3d84d93e5ff0347d2edab3332b5e0c2a7a7d4fc213884ecca`（临时输出未提交）。正式环境、Server2025/Debian未在本项证明；无客户数据/真实模型调用。

Known Issues：合成准入不代表真实审查或正式发行信任；Prompt 生产路由默认404，AI Invocation 资格还需独立验证；Gate3/UAT/可用程序包未通过。Next：`AI-03-A05-P04` 可选 HTTP 合同与隔离整链；正式路由须等待 CR-AI-007 信任前置。
