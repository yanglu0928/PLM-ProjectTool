# JOB-01-A04-P03：Document Parse Job Owner

2026-09-27 Phase 2，输入冻结 API-03、DM-03/04、Schema 0044及P01/P02真实来源验证。前置满足内部来源组合；当前权限与双Scope真实读取尚待验收，不开放运行组合。

本次先实现内部Owner：Jobs只读hint → Document/Audit真实提交来源 → Jobs完整引用锁定匹配，遵循Document先于Jobs锁序。当前会话/项目权限仍由AuthorizedJobReadService同UOW执行，不把来源证明当权限。返回仅安全JobOwnerProjection，不能下载、重试或写库。SUCCEEDED须另外核实际ParseRecord；未实现该证明前安全拒绝，不猜结果，也不标完整P03通过。

无Migration、API、角色、依赖或License变更。回滚撤内部Owner；不修改历史来源与队列。验收：原source与pair匹配、错Scope/actor/job/event/typed source拒绝、错误静态化、成功无证明拒绝、原授权服务及全后端回归。真实Session/双Scope/File-Version限制专项和成功结果仍是后续必做项，不缩减原Scope。

实施结果：内部DocumentParseJobReadProjection与6项单位测试、独立真实上传组合验证完成。Windows11/Python3.13.15全后端1191项无失败，2既有权限跳过；原真实PROJECT新版本/后继版本/故障恢复三次提交来源和锁定Queue pair读取匹配，九表前后无写。旧第一版本不因最新指针变化而失效。错typed source/原actor-Scope-project-job/event引用、安全错误、无真实结果的SUCCEEDED拒绝；GLOBAL仅单位坐标验证，不能当真实当前Admin权限证据。原上传提交/回放/回滚/故障恢复/字节验证随隔离fixture通过。

状态：SOURCE_COMPOSITION_INTERNAL_PASS，完整P03仍IN_PROGRESS。未挂运行Owner、无当前Session/GLOBAL实际授权验收、成功结果/File-Version限制专项未完成；本轮未运行wheel或性能/三平台/正式License/完整包验证。下一继续上述验收和真实ParseRecord原源证明，不能用本检查点替代原Scope。

后续权限验收（2026-09-27）：新增独立authority验证器，复用P02真实三次PROJECT和GLOBAL文件提交，在重复Audit歧义测试前注入可选observer，原P02默认行为不变。原不可变created_by不改写，原用户补TEST_ONLY credential和实际数据库Session；新增实际PM/IM/customer/admin/Department/Member事实。实际AuthorizedJobReadService与同UOW ProjectAuthorization/Document Owner读取，并经原可选ASGI GET重复验收，不用fake授权接口。

结果 AUTHORITY_HTTP_INTERNAL_PASS：四份真实commit源、PM/IM读他人metadata、customer只原creator、GLOBAL当前Admin、缺Session/未知Job/跨项目/Admin不绕项目、暂停成员/部门停用/用户停用/撤Session/撤Admin/测试License拒绝，十三表每次读取和拒绝前后不变。原第一Version实际转RESTRICTED、另一恢复提交的File实际转RESTRICTED，读取404；不可逆版本限制不假恢复，只在整体销毁的临时库。后继Version与GLOBAL仍正常读。HTTP实际state/strong ETag/no-store/null结果、If-None-Match不绕撤权、默认404/错误query400/host403通过。无正文、payload、path、lease/fence字段。

本轮仅验证脚本/文档，无生产代码或Schema/API/权限变化；unit1191/2跳过是上一检查点，本轮未重跑，wheel/性能/三平台未跑。原Upload/File/rollback/P02原源回归随fixture实际通过；TEST_ONLY credential非实际密码登录，License和原上传Access仍明确合成，不当正式部署PASS。成功ParseRecord来源证明、运行装配、完整Scope/Gate/程序包继续未完成；Next核真实SUCCEEDED ParseRecord，不能猜result_ref。
