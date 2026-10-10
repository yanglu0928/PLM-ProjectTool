# WFL-01-A07-P07-A07 Checklist 权威资格预览

## 结论

`PASS` —— 依 `CR-WFL-008` 实现了默认关闭的 Checklist 资格预览 Application/
HTTP 边界，解决前端无法安全构造冻结 PASS 请求的缺口，不改动既有冻结写
DTO。

## Changed

- 新增 `WorkflowChecklistQualificationPreviewService`，在一个事务中重验 License、
  Session、ProjectManager/ACTIVE Project、当前 Handover Workflow 和 Handover Owner 完整事实。
- 预览前后两次读 Workflow，事务中版本漂移返回 `CONFLICT_VERSION`；写时仍以
  强 ETag 和业务 Owner 再次复验。
- 新增 `GET .../workflow/checklist-items/{item_key}/qualification`，只返回写 DTO 所需
  Evidence 集、Workflow ETag 和最小 Review/Handover 引用；不暴露正文、路径、AI
  内容、锁版本、摘要或失败细节。
- 只允许两个已注册 Handover Item；无资格统一 409，默认 `create_app()` 继续 404。

## Files / Migration / API

- Application：`modules/workflow/application/preview_checklist_qualification.py`
- API：`modules/workflow/api/qualification_preview.py`、`entrypoints/api.py`
- Tests：新增 Application 单元和 HTTP 合同测试。
- Contract/CR：`workflow-checklist-qualification-v1-increment.md`、`CR-WFL-008`。
- Migration：无。
- API：新增兼容性 GET；原冻结 API 无变更。

## Tests

- 新增定向：9 项 PASS。
- Workflow/Project 相关：32 项 PASS。
- 后端全量：2763 项运行，3 项既有条件跳过，0 失败。
- 完整依赖环境：Python 3.13.15；首次精简环境因缺 `alembic` / `pgvector`
  产生导入错误，切换到项目完整依赖后全量重跑 PASS，不掩盖首次环境失败。
- 开发 wheel 包含两个新模块；SHA-256
  `c97424723d7698d249179422cfc3c9592b1acc3c8741fc363e92658bdc7c3e49`。

## Result / Known Issues / Next

- Result：`WFL_01_A07_P07_A07_QUALIFICATION_PREVIEW_PASS`。
- Known Issues：Router 尚未装入 Windows 生产组合，未做真实 PostgreSQL/HTTP 预览；性能门未验。
- Next：`WFL-01-A07-P07-A08` Windows 组合与真实 HTTP/PostgreSQL 资格预览闭环。
