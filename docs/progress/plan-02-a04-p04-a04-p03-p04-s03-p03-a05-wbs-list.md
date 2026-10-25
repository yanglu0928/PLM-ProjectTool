# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A05：PlanVersion WBS 项目成员分页读取

日期：2026-10-26。状态：`PASS_INTERNAL_WIN11_PG18_SYNTHETIC`；非Gate结论。

## 编码前检查

- 当前Phase：Phase 2 Platform Core。
- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A05`。
- 输入基线：冻结API-04 `PLAN_VERSION_WBS_LIST` / `WbsItemInput`、API-01 keyset cursor；A02 Owner/Schema、A04固定版本读取；Win11正式平台组合边界。
- 前置任务：A04 PlanVersion完整快照读取在Win11隔离PG18内部验收通过。
- 涉及模块：Plan API/Application/Infrastructure、Windows显式组合与Plan cursor Vault来源。
- 涉及实体：固定PlanVersion下WBS items、角色/条件及Requirement/Solution/Prototype/Evidence/里程碑固定引用。
- 涉及API：冻结 `GET /api/v1/projects/{project_id}/plans/{plan_id}/versions/{plan_version_id}/wbs-items`；无路径或字段Breaking Change。
- 涉及权限：Origin host + Session、Project成员只读授权和License事务复验；cursor绑定session、project、plan、固定version及page_size。
- 验收标准：只对固定版本查询；SQL使用keyset `(ordinal,wbs_item_id)`且上限200；重复/跨Session/Project/Plan/Version/page-size游标关闭；实际PG18双页无重复/遗漏并含WBS固定引用；默认应用不挂载。
- 风险：不使用可修改OFFSET；该版本不可变，组合序号稳定。无序关系排序不替代`PLAN_VERSION_GET`完整快照。
- 迁移/回滚：无Migration。回滚撤掉可选Router；数据保留。

## 实施结果

- 新增有状态范围绑定的HMAC cursor，payload区分`plan-version-wbs-list` family，并绑定Session摘要、Project/Plan/PlanVersion/page_size和末行ordinal/item ID。
- 复用既有Windows Plan cursor Vault key reference `project-plan-list-cursor-v1`，不新增Vault Secret；使用独立cursor family及不同字段集防止端点间重放。
- 新增应用层授权/License读取Owner及受限SQL keyset Repository，所有读取按project/plan/version联合限定，最多取page_size+1；Owned子数据批量读取，保留每item角色/条件/固定业务refs和milestone引用。
- 新增分页HTTP和Windows显式组合；默认App继续关闭该端点。

## 验证

- 定向Contract/cursor/Windows组合测试：`19 passed, 867 subtests passed`。
- 完整后端回归：`4134 passed, 3 skipped, 6190 subtests passed`。
- Win11隔离PG18真实PlanVersion创建后执行2个`page_size=1`页面，确认不同WBS ID、最终页`has_more=false`、跨Plan重放cursor拒绝；验证器输出`PLAN_VERSION_WBS_LIST_HTTP_POSTGRESQL_PASS`，依赖验收脚本exit 0。
- 非官方pgvector Windows构建仅用于项目外合成PG18测试，不进产品。

## 交付边界

- 无Migration；冻结API未变。
- 未实现WBS编辑、依赖管理、验证/送审和前端计划画布；按独立WBS推进。
- 本内部Win11/PG18组合结论不代表正式信任、真实客户、三平台、Gate 3、Pilot或正式Release。

## 文件

- `apps/backend/src/plm_assistant/modules/plan/api/wbs_list_cursor.py`
- `apps/backend/src/plm_assistant/modules/plan/api/list_plan_version_wbs.py`
- `apps/backend/src/plm_assistant/modules/plan/application/list_plan_version_wbs.py`
- `apps/backend/src/plm_assistant/modules/plan/infrastructure/plan_version_wbs_read_repository.py`
- `apps/backend/src/plm_assistant/entrypoints/windows_plan_cursor.py`
- `apps/backend/src/plm_assistant/entrypoints/windows_plan_version.py`
- `apps/backend/src/plm_assistant/entrypoints/api.py`
- `apps/backend/tests/contract/test_plan_version_wbs_list_api.py`
- `validation/plan-02-a04-p03-owner-transaction-pg/verify.py`
- `STATUS.md`
- `CHANGELOG.md`

## 完整性检查

- `git diff --check`：通过。
- Secret 检查：提交前按仓库 Skill 执行，未将 `.tmp/` 纳入本任务。
- 推送前必须 fetch 并核对远端分支；当前结论只限本WBS内部合成验收。
