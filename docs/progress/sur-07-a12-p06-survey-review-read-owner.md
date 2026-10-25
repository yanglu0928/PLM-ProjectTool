# SUR-07-A12-P06：Survey Review 读取 Owner

- 日期：2026-10-25
- 状态：`IN_PROGRESS`
- 依据：`CR-SUR-014`；P05 包内验收已阻断于缺失 Survey Review 读取 Owner。

## 编码前检查

- 当前 Phase：Phase 2 Platform Core。
- 当前 WBS：`SUR-07-A12-P06`，仅补齐 Survey Review 已冻结通用 GET/LIST 的只读 Owner 证明与 Windows 组合注册。
- 输入基线：Gate 2 冻结 `/api/v1`、CR-SUR-005/003、现有 SurveyReviewSubjectOwner、Handover/Outline Review Owner 模式；修订记录 `CR-SUR-014`。
- 前置任务：Survey Review 提交/通用 Review 内核通过；P04 前端 UI 通过；P05 暴露当前缺口但未通过。
- 涉及模块：Survey Application/Infrastructure；Windows PROJECT Review Read/List composition；Review Subject Registry 测试。
- 涉及实体：Survey、SurveyVersion、Review、ReviewRound、ProjectMember（只读）。
- 涉及 API：不增改合同；现有 `GET /api/v1/projects/{project_id}/reviews/{review_id}` 与 Review LIST 读取路径。
- 涉及权限：项目当前成员资格与活动 Survey/确切 SurveyVersion 所有权；写决定仍由通用 Review 对 PENDING 受指派 Reviewer 独立授权。
- 验收标准：成员可读取本项目活动 Survey 的 Review/活动固定版本；错误主体/错误版本/外项目/非成员失败关闭；Windows GET/List 组合实际注册 Survey Owner；没有决定写入；API Schema/Migration 不变。
- 风险：错误扩权或跨项目泄漏；负例与精确归属检查、PG HTTP 独立验证及包内 Edge 控制风险。
- 变更：CR-SUR-014 先记录了原因、方案、风险、兼容、回滚和验证，再执行本 WBS。

## 预计文件

Survey Review subject application/repository、Windows Review composition、定向单元/集成验收、此进度记录、`STATUS.md`、`CHANGELOG.md`。

## 当前执行与验收记录

- 已实现 `authorize_read`：通过当前 ACTIVE 项目成员资格，证明当前 Survey 为 ACTIVE；有版本请求时进一步证明精确 SurveyVersion 属于同一项目和 Survey。读取权限不依赖是否被指派，决定权限不变。
- 已补 `active_version_exists` 查询并把 Survey Owner 注册到独立 Windows PROJECT Review GET 与 LIST 组合；不涉及通用写命令、API载荷、Schema、Migration或产品依赖。
- 定向测试：Survey Owner、Review Registry、Windows Review composition、Review Read Service 共34项通过。
- 后端全量：4102 passed、3 skipped、6153 subtests passed；`compileall`、`git diff --check` 通过。
- 旧 standalone PG 验证入口启动失败：本机测试 PG 端口连接超时（服务未监听）；没有产品测试断言失败。新包内 Edge/HTTPS/PG18 验收还需重建候选执行，故本 WBS 尚未标 PASS。
- 验收偏差：P03 曾认定后端 Review Owner/GET 已注册，实际只覆盖送审写 Owner，未核对读取 Owner Registry；此结论已更正并在 CR-SUR-014 追溯。
- 候选构建偏差：首轮打包器因 Git pathspec 过滤失败，把保留的 `.tmp/` 解包文件误报为源码污染。修正候选清洁检查为递归排除 `.tmp/**`，回归测试6/6通过；保留所有 scratch 数据。该构建工具修正已记录在 CR-SUR-014，待提交后继续干净候选构建。
