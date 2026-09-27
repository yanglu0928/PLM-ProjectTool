# JOB-01-A04-P03：Document Parse Job Owner

2026-09-27 Phase 2，输入冻结 API-03、DM-03/04、Schema 0044及P01/P02真实来源验证。前置满足内部来源组合；当前权限与双Scope真实读取尚待验收，不开放运行组合。

本次先实现内部Owner：Jobs只读hint → Document/Audit真实提交来源 → Jobs完整引用锁定匹配，遵循Document先于Jobs锁序。当前会话/项目权限仍由AuthorizedJobReadService同UOW执行，不把来源证明当权限。返回仅安全JobOwnerProjection，不能下载、重试或写库。SUCCEEDED须另外核实际ParseRecord；未实现该证明前安全拒绝，不猜结果，也不标完整P03通过。

无Migration、API、角色、依赖或License变更。回滚撤内部Owner；不修改历史来源与队列。验收：原source与pair匹配、错Scope/actor/job/event/typed source拒绝、错误静态化、成功无证明拒绝、原授权服务及全后端回归。真实Session/双Scope/File-Version限制专项和成功结果仍是后续必做项，不缩减原Scope。

实施结果：内部DocumentParseJobReadProjection与6项单位测试、独立真实上传组合验证完成。Windows11/Python3.13.15全后端1191项无失败，2既有权限跳过；原真实PROJECT新版本/后继版本/故障恢复三次提交来源和锁定Queue pair读取匹配，九表前后无写。旧第一版本不因最新指针变化而失效。错typed source/原actor-Scope-project-job/event引用、安全错误、无真实结果的SUCCEEDED拒绝；GLOBAL仅单位坐标验证，不能当真实当前Admin权限证据。原上传提交/回放/回滚/故障恢复/字节验证随隔离fixture通过。

状态：SOURCE_COMPOSITION_INTERNAL_PASS，完整P03仍IN_PROGRESS。未挂运行Owner、无当前Session/GLOBAL实际授权验收、成功结果/File-Version限制专项未完成；本轮未运行wheel或性能/三平台/正式License/完整包验证。下一继续上述验收和真实ParseRecord原源证明，不能用本检查点替代原Scope。
