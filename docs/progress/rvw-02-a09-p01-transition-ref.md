# RVW-02-A09-P01：不可变首次决定/撤回结果

日期2026-09-26；Phase2；版本0.1.0.dev0；Result：INTERNAL_REF_PASS，A09完整授权幂等入口尚未完成。

## 编码前检查 / Changed / Files

输入冻结AF-02/API-02、0035、A08内部事务命令、通用receipt仅存Ref结构。首次决定可能partial，后来终态/新Round不能使重放响应变成当前投影。按DEC-20260926-183先补稳定事件Ref，没有删减权限/幂等Scope。

`application/persist_transition.py` 的 AppliedReviewTransitionRef 添加非零event_id，owned insert RETURNING真实不可变事件ID；`infrastructure/transition_repository.py` 新get_transition_ref只取范围内DECISION_RECORDED/WITHDRAWN事件，拒绝STARTED/COMPLETED。复用完整历史快照，核对Actor/决定映射、连续版本、前轮封口与集合前缀状态，计算首次根版本=round_no+前轮lock_version之和+事件after_version。后续Round不影响旧版本/状态/时间。需可信当前权限的调用方事务，不创建收据或授权、不写入/commit。原Query可返回旧Round与当前根不同状态，不当真实Sources/批准证明。

修改A08unit构造以绑定新增ID，新增6项 `tests/unit/test_review_transition_ref.py`；新增 `validation/rvw-02-a09-p01-transition-ref/verify.py`。前置设计与STATUS/决策/版本说明同步。

## Tests / Result

- Windows11/Python3.13：757项后端无失败，2项既有符号链接权限环境跳过。unit覆盖首次partial/终态/撤回、版本前缀错位/错误状态/前轮未封口/Actor损坏/无ID拒绝。
- 隔离UUID PostgreSQL：第一轮RETURN仍partial/全部后RETURNED；第二轮partial后中文原因撤回；第三轮开始后四个旧Ref的Actor/状态/原始计数/时间/Version完全相等。非命令事件/跨项目/其他根/轮次/不存在引用拒绝；重复查询完整八表/Sources/Audit快照不变。
- A08真实owned/Audit/合成消费故障回滚和竞争单终态回归、真实Session受权送审/幂等/40P01恢复回归PASS。
- 开发wheel PASS，SHA256 `39c46f63401f1ee7469ae4db667230a61137bab9685aa6b07b64ffefa6b2719e`，不是正式安装包。

该新历史Ref verifier中SyntheticOwner明确TEST ONLY no-op，不验证实际客户/内容/业务锁或正式指针；仅检验owned不可变历史还原。本轮无新授权、receipt或HTTP验收。隔离库finally清理，未写生产环境。

## Migration / API / Compatibility / Upgrade

无新增Schema/API/角色/依赖改变，需0035，升级无动作；内部DTO尚未公开、正式外部决定/撤回收据未创建，不需迁移外部响应。0034/0035历史保留。目标Win11/Server2025/Debian13不变，本轮仅Win11，Server未验、Debian暂不验。

## Known Issues / Next

A09-P02新增当前Session/CSRF/Project/assigned reviewer或PM权限、真实receipt绑定event_id/指纹；重放当前固定旧版Owner访问重验，禁止再次consume/Audit。未知Owner失败关闭，最终命令需整事务回滚/并发/死锁恢复验收。实际Owner/客户批准/HTTP/Gate3/UAT/正式可用程序包未完成，目标继续。
