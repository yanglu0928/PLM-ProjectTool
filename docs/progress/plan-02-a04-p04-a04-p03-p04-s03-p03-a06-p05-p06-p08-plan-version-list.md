# A06-P05-P06-P08 PlanVersion 冻结版本历史分页

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P08`
- 结果：`PASS_SCOPE_LIMITED`

## 变更

- 补齐冻结 API-04 `PLAN_VERSION_LIST GET /api/v1/projects/{project_id}/plans/{plan_id}/versions`，包括应用服务、只读 SQL Repository、响应投影、严格 query 和签名 keyset cursor。
- 每个摘要只返回不可变版本身份/版本号/状态、supersedes/Review refs、创建人和时间，不返回版本正文；按 `version_no DESC` 分页，项目及 Plan 双重作用域过滤。
- 增加 `PLAN_VERSION_LIST` Project member 非写授权策略。显式 Windows `include_secret_read` 组合使用既有 Credential Manager Plan cursor key 和独立 family；default/create_app 与 login-only 模式不挂载。
- 无 ORM、Schema、Migration、冻结 API Contract 或业务数据变化。旧 P06-P05/P06-P07进度判断保留为历史，由 P06-P08纠正记录更正，不覆盖历史。

## 验收

- 定向 API/cursor/Windows composition/授权合同：19 passed、875 subtests passed。
- 完整后端：4190 passed、3 skipped、6219 subtests passed。
- Windows 11 隔离 PostgreSQL 18：升级到 head、`alembic check`无漂移；真实SQL Repository经HTTP两页读取3个合成PlanVersion，降序 `[3,2,1]`、无重复；跨Plan cursor被拒绝。另一合法Plan空列表不泄漏版本数据。临时数据库/实例已清理。
- 隔离组合的Session、License与Project Authorization使用合成替身；未宣称真实正式信任/授权验收。默认应用404与显式平台只读挂载401合同通过。
- Windows 11 backend wheel构建成功，文件位于`apps/backend/dist/plm_project_tool_backend-0.1.0.dev0-py3-none-any.whl`，并检查确认包含新增四个PlanVersion列表模块。构建临时目录指向D盘`D:\PLM-Test-Temp`。

## 偏差与限制

- 首次全量测试发现生产登录组合合同夹具未为新增只读Cursor factory提供构造替身，以及授权矩阵固定数量断言需更新；已修正夹具和精确矩阵断言，重跑全量通过。
- 初次尝试wheel时发现backend `.venv`未装pip/build；通过本地ensurepip补齐pip、在该venv安装build工具后完成wheel构建。未改项目依赖清单；安装环境为D盘项目虚拟环境，构建临时目录也在D盘。
- 本项不代表 Gate 3、Pilot、正式 Release 或真实项目数据验收。

## 下一项

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P09`：将已有 PlanVersion create/read/write Client 与本次版本历史读取接成独立用户页面，优先实现列表导航和固定版本查看，再完成不可变草稿创建；Validate/Review工作流保持独立切片。
