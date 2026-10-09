# SOL-03-A04-P03-P03-P06-A02-P02：GLOBAL 候选安全读取前置核查

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P06_A02_P02_PRECONDITION_BLOCKED`；仅设计/证据核查，未开放项目成员 GLOBAL 读取，也未通过双 Scope 前端验收。

编码前检查：Phase 2 / 本 WBS；输入为 Gate2 双 Scope CREATE、CR-SOL-018、DEC-1144 与当前 GLOBAL 管理读取；前置缺“可向项目成员展示”的受审定标签和独立授权读面。涉及 Solution/Project、GLOBAL ReferenceRoot/Version 和既有管理员 GET/LIST；拟增项目上下文候选 GET，PM/IM 可读，管理员发布仍独立。验收须先完成发布账本 ORM/Migration/空及有数据升级降级、管理员审定/撤回 Audit、候选权限/脱敏/现时资格/分页、Win11 PG/浏览器。风险为原始名称或来源信息泄漏、旧版本/失效资格仍可见。

核查证据：`GlobalReferenceReadService` 仅接受部署管理员；其列表投影包含 `Root.name`，而 GLOBAL 创建没有项目可见性审定。现有 OutlineVersion 服务端能够安全使用固定 GLOBAL UUID，但这不赋予项目用户普通管理读取权。以 UUID 前缀替代标签也无法支撑有意义的人工核对。按 CR-SOL-018/DEC-1145 先做版本绑定、可撤回、历史留存的管理员审定非敏感发布，再做窄投影；旧数据不默认发布。当前不改 Schema/API/权限，未运行代码测试；静态检查得出前置不满足。P06-PROJECT 子集保持可用，完整 P06/Gate3 不关闭；转向独立 `SOL-03-A05-A01` 版本读取 Owner。
