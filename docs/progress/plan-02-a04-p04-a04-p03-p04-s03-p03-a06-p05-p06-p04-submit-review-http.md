# A06-P05-P06-P04 PlanVersion SubmitReview HTTP

- 日期：2026-10-26
- WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P04`
- 结果：`PASS_SCOPE_LIMITED`

## Changed

- 新增冻结`PLAN_VERSION_SUBMIT_REVIEW` HTTP适配器：固定API-04路径；精确四字段body、未知字段/重复JSON键拒绝；policy固定`PLAN_VERSION_ALL_V1`，due_at与submission_note只接受显式null；使用canonical路径/Reviewer UUID、可信Origin、Session/CSRF、Idempotency-Key和标准错误Envelope。
- 201响应仅投影Review/Round、Project/Plan/PlanVersion固定引用、策略/Reviewer和提交者/时间，`ETag: "v1"`与`Cache-Control: no-store`；不输出正文或内部表信息。
- Windows显式write组合复用同一个PlanVersionValidationService实例为当前来源Evaluator，将新路由合入既有Plan validation router；普通默认/login-only组合保持未挂载。未改冻结API或Schema/Migration。

## 验证

- 定向API/Windows composition/ProductionLogin合同：`71 passed, 29 subtests passed`。覆盖默认404、可信Origin/CSRF、请求字段、due_at/note/policy、错误映射及显式write组合挂载。
- Windows 11 / PostgreSQL 18.6隔离链：完整迁移/drift；真实HTTP调用Plan submit-review，Session/Project授权/License/Reviewer及当前Approved来源Evaluator用合成替身；数据库真实写入Review/Round/START、PlanVersion 0190结果、Audit和Receipt。HTTP同Key重放保持完整不可变`data`和ETag不变、trace_id为本次请求值。随后由真实Registry路由批准两版并替换Approved指针、撤回第三版并保持指针；Audit故障全事务回滚；真实撤回历史降级拒绝。
- 全量后端：`4184 passed, 3 skipped, 6206 subtests passed`。
- `git diff --check`通过，修改文件Secret扫描无匹配。本项无客户正文外发、正式数据库访问或外部AI调用。

## 偏差 / 限制

- 首轮验收将整个HTTP回执（含`trace_id`）作相等比较失败：标准Envelope的trace_id按请求新生成，符合协议；验收调整为要求不可变业务data与ETag完全相等，并确认每次trace_id独立。
- PG脚本使用Review/Plan真实持久化与触发器，但Session、License、PM/项目授权、Reviewer资格、当前Approved业务来源Evaluator为确定性替身；不代表正式信任或真实客户送审。
- 没有运行Edge/浏览器，也没有为PlanVersion开发页面；完整可用UI、Gate、Pilot及Release仍未完成。

## Next

`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P05-P06-P05`：先检查现有Plan列表/详情页面与API客户端，规划PlanVersion创建、读取、校验和原子送审的用户流程；只消费既有冻结端点，不重复构造Review分步写请求。按UI单一验收切片实现，再做Windows 11 Edge→显式ProductionLogin/隔离PG用户合成链。
