# SUR-07-A11：调研版本原子送审与客户评审人选择

日期：2026-10-25；结果：`SUR_07_A11_FRONTEND_PASS`。

## 编码前检查

| 项目 | 内容 |
|---|---|
| Phase/WBS | Phase 2 / `SUR-07-A11`，完成 Survey Version 原子送审前端单一闭环。 |
| 输入基线 | 冻结 Survey `:submit-review` 与 `SURVEY_ALL_V1`；后端 ProjectManager/来源/成员资格事务重验、Review 创建和版本状态转换已实现。 |
| 前置任务 | `SUR-07-A09` 前置核查、`SUR-07-A10` Validate 报告入口完成。 |
| 涉及模块 | Session 私有 Survey submit-review 路径、Survey 送审客户端、ProjectMemberReadClient、Survey 详情送审面板。 |
| 实体/API/权限 | SurveyVersion、ProjectMember、ProjectReview；`POST /api/v1/projects/{project}/surveys/{survey}/versions/{version}:submit-review`；仅 Project Manager 可送审，Reviewer 必须是当前 ACTIVE `CUSTOMER_MANAGER` / `CUSTOMER_MEMBER`。 |
| 验收标准 | 完整分页且重复游标/重复成员/超过分页上限失败关闭；只允许选择最多32名当前客户成员；请求固定策略和 null 可选字段；显式确认；严格校验201回执、`SRV-02`、评审人快照、IN_REVIEW/ETag；不确定结果保存原集合和幂等Key同号重试。 |
| 风险 | 页面候选资格是读取时快照；服务端仍须事务重验。成功仅代表进入 IN_REVIEW，不代表客户批准。 |

## 变更

- Session 私有写桥调用冻结原子 Survey Version submit-review；不使用通用 Review 两步写接口。
- 新增严格送审客户端：核对会话 ProjectManager 权限、唯一且最多32位候选、请求/回执合同、审计追踪与 ETag。
- Survey 详情仅对有权 PM 显示读取成员、选择客户评审人、显式确认的面板；成员列表必须读完最多20页（每页最多50）才允许送审。
- 幂等Key与原评审人集合保存在当前浏览器 Session Storage。传输/服务器不确定时锁定选择并要求先核对，再显式同号重试；有确定失败才清除 pending。
- 无 Schema/Migration/API 合同/License/依赖变更。无数据库迁移。

## 验证

- Survey详情与Session定向：178项通过，覆盖报告面板、当前客户候选读取及原子送审201回执。
- 前端全量测试：2041项通过（192文件）；类型检查通过；399/402模块构建通过，现有 >500 kB 主包警告仍在。
- 后端合同、PostgreSQL 临时库、Windows真实组合运行未在此 WBS 重跑；Server 2025、Debian 13、真实客户评审/UAT及正式信任未因此通过。

下一项：按 `STATUS.md` 继续调研 `P05-P04` 自然失效/撤销负例，以及 Survey 在完整纵向链中的实际浏览器/服务装配验收。Pilot、Gate 3、正式发行仍未通过。
