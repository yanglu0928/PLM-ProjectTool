# SOL-06-A09-P06-P02：专项创建页面

- 日期/版本：2026-10-12 / `0.1.0-dev.0`。TraceLink：冻结 API-04 SOL_SPEC_CREATE → A09-P03 Owner/P04 HTTP/P05 Windows/P06-P01 受控命令 → 本项。Phase 2。
- 编码前检查：前置写链、SessionClient 与 Requirement/Section/SectionVersion/Evidence 只读候选已存在；仅添加 Solution UI 页面/路由/候选组合，不变更数据层、服务端授权或冻结 API。验收须证明可选当前固定来源、四类提示表单、DRAFT 人工确认、断线同号恢复和角色隔离。
- Changed：按页读取当前已批准需求、活动章节最新可用 DRAFT/IN_REVIEW/APPROVED（不适用时回退当前已批准固定版本）、合格项目证据；若分页/跨项目/重复身份不一致则失败关闭。项目成员从章节固定详情进入创建页，四类专项各有字段说明和示例，不需手写 JSON/UUID；流程页当前只构造线性图。提交前记录原 Key/正文于会话存储，不确定结果重试需再次人工勾选，提交成功只展示 DRAFT 编号，不称已批准。
- Verification：候选、四类 payload 表单、页面定向 10 项；候选当前批准版 fallback 修正后定向 7 项；其后前端全量 138 文件/1775 项、typecheck/生产 build 复跑通过。未运行真实 Edge/PG 页面提交，故只标页面合同 PASS。
- 风险/回滚：候选快照可能失效，后端 Owner 写前重验；页面不显示无可信来源的真实附件引用。复杂非线性流程编辑、专项 GET/Review/送审/OutputArtifact/Trace/Section ready_for_review 后续独立 WBS。撤页面路由/入口即可回滚，不删历史。Gate3/Pilot/Release 仍未通过。
