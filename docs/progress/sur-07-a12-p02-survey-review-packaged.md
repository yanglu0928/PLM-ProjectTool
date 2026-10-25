# SUR-07-A12-P02：Survey Validate→原子送审固定包验收

- 日期/版本：2026-10-25 / `0.1.0-dev.0`。
- 状态：`SUR_07_A12_P02_PACKAGED_VALIDATE_SUBMIT_PASS`。本项仅证明 Windows 11 非发行候选中的合成纵向验收；没有客户事实、客户决定或正式发行结论。
- TraceLink：冻结 Survey `:validate` 与 `:submit-review` API / Owner、`SURVEY_ALL_V1` → SUR-07 A10/A11 → A12-P01 前置核查 → 本项。

## 验收结果

- 从干净提交 `4e40831e80f17ea871f06bb36d4f755b17b6d55f` 重新构建候选，包：`artifacts/package-prep/windows11/current-app-sur-a12-p02-20261025/current-app-candidate-8adf38286419/NOT-FOR-RELEASE-windows11-current-app.zip`；SHA-256 `730f87b6ddf87d429ada7a28c2e6a3ae7de85ba9c3ba7a042a408c2f86a367e5`；22,197 个负载文件。父候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98`；pgvector wheel SHA-256 `fedc9800894e6da2be51358d7b7c574bf34f247ca741a5a09513622135f5964f`；后端 wheel SHA-256 `d593f4c89fffdc7724c15262a86f83f1dae46ec02f432fab04055ec206aa8c8a`。
- 候选独立清洁解包和逐文件 SHA-256 通过；负载 22,197 件。当前 Windows 11 上使用包内 Python/FastAPI、PostgreSQL 18 与 Caddy/HTTPS，通过真实 Edge 建立合成交接来源和 Survey 定义/版本。
- Edge 完成固定 DRAFT 的当前来源 Validate（bodyless POST、CSRF、幂等键；响应 `valid=true`、1 个问题、2 个来源与审计 ID），再由具有 `PROJECT_MANAGER` 角色的合成项目成员显式选取一个 ACTIVE 客户角色 Reviewer 并提交 `SURVEY_ALL_V1` 原子送审。HTTP 返回 201、状态 `IN_REVIEW`，UI 明示“尚未批准”。
- 独立 PostgreSQL 查询确认 SurveyVersion/Review/Round 的 ID 与状态一致，唯一 ACTIVE 客户 Reviewer 快照为 PENDING，Validate/Review Audit 和 `V1_SURVEY_VERSION_SUBMIT_REVIEW` 幂等收据各一条；决定数为 0，Survey `current_approved_version_ref` 仍为 NULL。旧 ETag 的后续写请求被 `409 CONFLICT_VERSION` 拒绝；既有匿名/跨项目/非授权拒绝回归通过。
- 固定候选 SHA 前后不变。验收输出：`SYNTHETIC_CURRENT_APP_PACKAGED_HTTPS_PASS`、`temporary_processes_stopped=true`、`temporary_files_removed=true`、`synthetic_vault_targets_absent=true`、`vault_key_count=48`；说明 48 个本地测试 Vault 目标均已清理。正式信任材料没有注入。

## 偏差与失败重试记录

- 没有修改产品代码、冻结 API/Schema/Migration、License 行为或生产依赖；没有产生需要正式 Change Request 的基线偏差。唯一源文件变化是可重复验收脚本。
- 候选 wheel 首次尝试因后端虚拟环境没有 `build`/`pip` 且系统 Python 缺少 setuptools 而失败；随后仅在 `D:\PLMReviewTemp\plm-build-deps-sur-a12-p02` 使用 build-only `setuptools 84.2.1` 完成 wheel 构建，没有加入生产依赖或改变依赖清单。
- 前置暂存调用一次因未指定既定 ASCII Temp 父目录而安全拒绝；两次 smoke 调用因临时目录不满足既有命名/父目录规则，在业务测试前退出。没有触碰正式安装路径。
- 浏览器/断言验收的未通过运行均保留：首次在 Survey 版本列表异步加载前点击；随后发现测试模块动态加载后的合成 ProjectManager 角色注入未命中真实回调命名空间，送审按钮被产品正确隐藏；另有一次上游 Edge 调试目标在旧 12 秒窗口未就绪，因此其等待从 12 秒提高到 30 秒；送审实际返回 201 后，测试又错误要求合同未规定的 `If-Match`，以及错误期待送审改变 Survey ETag 后的来源负例仍返回旧的 422。逐项修正测试同步/夹具/等待/断言后，最后一轮完整链和数据库断言通过。
- 最终候选 `release_eligible=false`、`legal_clearance=false`、`formal_trust_provisioned=false`。Server 2025/Debian 13、正式签名信任、正式离线安装/升级、客户真实评审与客户批准、UAT、Gate 3～7、Pilot 和三平台正式发行均未因此通过。

## 变更与后续

- Changed：仅增加当前 Survey 包内 Edge/PG18 验收覆盖并按真实冻结合同修正测试断言；未改变产品兼容性和升级方式。
- Files：本记录、`validation/sur-07-a08-survey-version-packaged/verify.py`、`validation/sur-07-a08-survey-version-packaged/run-survey-version-edge.mjs`、`validation/hnd-05-a02-p04-version-packaged/run-handover-version-edge.mjs`、`STATUS.md`、`CHANGELOG.md`。
- 验证：Python 编译检查、两个 Node 脚本语法检查、候选清洁解包和本项完整 Windows 11 Edge/HTTPS/PG18 纵向验收通过。前端产品源码未变化；此项不重报先前 A10/A11 前端全量测试结果。
- Next：执行 `SUR-07-A12-P03` 编码前只读核查：确认 Review 页面/API 是否支持 `SRV-02` / `SURVEY_ALL_V1`，以及人工 Reviewer 决定流程的安全 UI 缺口；不得用合成账户决定冒充客户决定。Pilot/Gate/Release 继续独立开放。
