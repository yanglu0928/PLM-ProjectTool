# A06-P05-P06-P03 PlanVersion Review Registry / Windows 显式组合

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P03`
- 结果：`PASS_SCOPE_LIMITED`

## Changed

- Windows PlanVersion validation composition现在返回其Router与同一个ValidationService实例；显式PROJECT Review组合复用该实例作为终态当前来源Evaluator。
- `PLN-02` PlanVersion Owner仅在显式Windows PROJECT Review写组合可选注册；默认组合不提供evaluator即不注册。production login的显式write分支把Plan Validate服务实例传给Review composition；未改冻结API、未增加专用Review路由。
- PG18验收器经`ProjectReviewSubjectRegistry`实际分发Submit/Start/terminal回调。

## Tests / Verification

- 定向：windows Review composition、PlanVersion validation composition、production login合同共59 passed/29 subtests。
- Win11 / 隔离PG18.6：完整迁移/drift；经真实Registry和Review/Plan Owner连续提交并批准两版、旧版SUPERSEDED及批准指针切换，创建第三版并撤回，PlanVersion `RETURNED`且原Approved指针保留；Review/Plan Audit与Receipt、同Key精确重放；Plan终态Audit注入失败使Review事件、Plan结果、Receipt整体回滚；含真实撤回历史的0210降级被拒绝，版本号仍为0210。
- 完整后端：`4172 passed, 3 skipped, 6206 subtests passed`。
- production_login契约测试证明ValidationService实例传入显式PROJECT Review composition。Windows组合依赖装配由组合单测覆盖；PG持久化脚本直接组装Registry/Owner，不是完整Windows HTTP/Edge链。

## API / Migration / Known Issues

- API：无新增或Breaking API；复用冻结Review命令端点。独立原子`:submit-review` HTTP命令仍未实现，不能用通用Review串行调用替代冻结业务Operation。
- Migration：无新增（使用0210/0200/0190）。
- Session/License/Project策略/Reviewer身份/来源当前验证器在隔离PG脚本中使用替身；真正安装信任锚、生产服务身份、真实业务来源和客户确认未验证。此结果不代表Gate、Pilot或Release。
- `git diff --check`通过；本片Secret扫描无匹配。`.tmp/`未触碰。

## Next

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P04`：为冻结`PLAN_VERSION_SUBMIT_REVIEW` Operation实现独立原子HTTP边界与Windows显式挂载；先核对API-04、错误Envelope、Session/CSRF/Origin、幂等与响应合同。不能将通用Review Create/Start两个请求伪装成该业务操作。
