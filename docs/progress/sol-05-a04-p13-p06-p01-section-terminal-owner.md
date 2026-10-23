# SOL-05-A04-P13-P06-P01：Section Review 终态 Owner 与 Windows 合成验收

日期：2026-10-23。状态：`INTERNAL_PASS`（合成客户/项目数据）；不代表真实客户签署、Gate 3 或 Pilot 可用。

## 编码前检查与偏差

- 输入：Gate 2 原冻结基线、CR-SOL-024、0183/0184 受控 Section Review 状态、P13-P05-P04 的 IN_REVIEW 当前六维证明、统一 Review Engine 的终态合同。
- 单一问题：指定客户确认人的决定如何在同一事务受控形成 SectionVersion 的 APPROVED/RETURNED，负责人撤回如何形成 RETURNED，并维持精确 Review/Round/内容指纹、批准指针、结果历史、Audit 与幂等。
- 无新 Schema/公开 API/License 权益；Windows 显式 Review 命令/读/列表注册 SOL-05 Subject Owner，默认/只读写入口仍关闭。
- 实测发现原 Section Evidence 内部来源图限制实施方角色，客户确认人批准时 `evidence=UNAVAILABLE`。实施前登记 `docs/changes/CR-SOL-025-section-terminal-evidence-proof-role.md`：仅终态内部只读重证使用同项目成员角色，原 VALIDATE/送审及公开证据权限不扩大，返回仍仅为状态事实。

## 实现与验收

- Owner 在每次决定核对当前最新 IN_REVIEW、Review Identity/Round、固定版本指纹与指针；批准还重证六维全 PASS、客户 Reviewer 当前角色。退回/撤回不把版本或旧批准指针当新批准。
- SQL 同事务写入 Version 状态、先前批准版 SUPERSEDED、Section 指针和 lock_version、不可变 Review 结果；之后独立反查终态结果/状态/批准数。DB 0184 Guard/闭合触发器保持启用。Review Engine 负责客户决定、Review/Round/Event/收据，Owner 追加 Section Audit。
- 定向单元/组合验证通过；后端全量 `3983 passed, 3 skipped, 6079 subtests passed`。
- `validation/sol-05-a04-p13-p06-p01-section-terminal-windows/verify.py` 在 Windows 11/一次性 PostgreSQL 18.6 中使用合成账户三次独立运行：指定合成客户批准、退回及项目负责人撤回均真实 HTTP/PG 成功、同 Key 回放一致、版本/指针/Review 决定/结果可反查；批准前撤销 Trace 得 404 且无决定，恢复 Trace 后才批准。脚本 exit 0。

## 限制、兼容与回滚

- 仅合成客户决定，绝不视为实际客户确认或正式质量/UAT。尚未验证前端真实浏览器操作及完整业务链输出、正式服务信任和离线安装；Pilot/Gate 3/Release 仍 NOT_READY。
- 不改变现有 `/api/v1` 合同或数据库结构，旧 DRAFT/送审记录不重写。若需回滚，关闭显式 Section Review 注册并前滚修复；既有 Review/结果/Audit 不可删除。CR-SOL-025 的内部客户证据资格不等于授权客户访问证据原文。
- 下一项 `SOL-05-A04-P13-P06-P02`：核查并接通客户 Section Review 前端/真实浏览器与 Review 列表/详情，保留合成/真实客户事实区分。
