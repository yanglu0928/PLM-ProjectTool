# SOL-06-A11-P01：结构化专项列表前置核查

- 日期/版本：2026-10-16 / `0.1.0-dev.0`。TraceLink：Gate 2 冻结 API-04 `SOL_SPEC_LIST` → SOL-06 0161～0164 → A09 创建/A10 详情 → 本项；决策见 `DEC-20261016-1206`。当前 Phase 2。
- 编码前检查：专项完整 DRAFT、项目成员详情权限和 Windows 读写组合均已验证。涉及 Solution 只读列表、ProjectId 隔离、专用游标与前端可发现性；不改 Schema、冻结路径、写权限、License 权益或历史。验收需覆盖空页、多 series/多版本、稳定翻页、并发新增、项目/会话/查询绑定、跨项目与失效 Session。
- 基线结论：冻结结果明确为 `Spec version page`，且没有独立 series/versions 子路径，因此列表返回项目内全部不可变版本，不只返回每个 series 的最新版本；每项为最小摘要，详情仍由 `SOL_SPEC_GET` 读取完整载荷/引用。页面可按 series 分组和标记最新版本，但不得隐藏历史或把 DRAFT 当正式方案。
- 分页结论：按服务器生成的 UUIDv7 `structured_solution_spec_id DESC` 做 keyset；游标独立于其他 Solution 列表密钥，并绑定 family、Session 摘要、ProjectId、page_size 及未来显式过滤条件。新版本插入发生在游标边界之后，不会让既有后续页重复；不以客户端时间或可变状态作为位置。
- 权限/完整性：新增独立内部操作 `SOL_STRUCTURED_SPEC_LIST`，角色仍为所有当前项目成员且采用锁定读；不得借用 CREATE。Repository 必须限定 ProjectId、只投影 Root+payload 完整性摘要并验证 version/review/指纹/时间等边界；不存在/无权统一防枚举。列表不推断来源当前仍合格或 Review 已通过。
- 实施拆分：P02 内部摘要/Repository/授权读取与可弃 PG 验收；P03 专用签名游标；P04 默认关闭 HTTP；P05 Windows 组合；P06 前端列表/入口；P07 Edge→真实 HTTP/PG。每项独立验收并保留默认关闭/失败关闭。
- 验证：静态交叉核对冻结 API-04、DM-05、SC-02 UUIDv7 规则、当前 ORM/0164、项目授权表及 Section/Outline 列表先例；未运行新的程序测试。本项仅定界，不声称列表已实现。
- 限制：专项修订/验证/送审、OutputArtifact、章节六维 `ready_for_review`、正式信任、性能、Server 2025/Debian 13、Gate 3/Pilot/正式 Release 均未因本核查通过。
- Next：`SOL-06-A11-P02` 实现项目内全部专项版本的受权摘要读取与 PostgreSQL keyset 结果，先不开放 HTTP。
