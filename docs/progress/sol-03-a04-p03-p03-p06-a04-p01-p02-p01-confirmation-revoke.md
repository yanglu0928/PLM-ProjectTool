# SOL-03-A04-P03-P03-P06-A04-P01-P02-P01：确认撤销后候选与 CREATE 直接拒绝

日期：2026-10-09。结果：Win11 可弃 PostgreSQL 18.6/真实项目 HTTP 和管理员确认撤销服务通过；只证明撤销，不推定到期时间边界。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate2 API-04、CR-SOL-018、DEC-1160/1162 与已验候选/CREATE/真实确认账本。
- 单一问题：在 Reference ELIGIBLE、项目成员和所有 Document/Evidence 均仍有效时，撤销最新 GLOBAL 脱敏确认是否立即隐藏候选并拒绝旧固定引用的创建。
- 模块/实体/API/权限：仅验证资产；真实 `ReferenceDeidentificationRevokeService`、项目候选 GET 与 OutlineVersion CREATE 现有服务，不改运行实体/API/角色、ORM/Migration 或依赖。
- 验收：撤销前项目 GET 200 可见，真实管理员撤销后 GET 200 空项、原选择 CREATE 503，无版本/创建 Audit/创建收据，撤销 Audit 恰一条；隔离 PG 无残留。
- 风险：上游来源夹具原顺序为先撤 Evidence 后撤确认，无法单独归因。此脚本在其余条件有效时撤销，并在断言后以特定成功哨兵结束该可弃夹具；不修改客户或正式数据。

## 验证

新增 `validation/sol-03-a04-p03-p03-p06-a04-p01-p02-p01-confirmation-revoke/verify.py`。脚本复用真实来源、发布、项目 PM 和 Windows 路由工厂；在无其他失效事件前，使用真实管理员 Session/CSRF/License 调用确认撤销 Owner，再经项目真实 ASGI/PG 查询和提交原固定版本。结果：撤销前 GET 200 返回该候选；撤销后 GET 200 `items=[]`；OutlineVersion CREATE 503；0 个该目录版本、0 个创建 Audit、0 个创建收据，且确认撤销 Audit 1 条。执行退出码 0，输出 `GLOBAL_CANDIDATE_CONFIRMATION_REVOKE_PASS` 与本 WBS PASS。上游来源夹具在本项成功哨兵处停止，不能将其后续 Evidence 撤权自测计入本项；临时 PG 由外层 finally 停止/清理。

兼容/升级/回滚：只增验证资产，无 Schema/Migration、应用 API/权限/依赖变化；删除脚本即可回滚，历史证据保留。下一项 P02-P02 用隔离时钟/真实 PG 确认“已过期”边界，P01-P03 测版本修订；CR-SOL-018/Gate3 不关闭。正式服务账户、Server2025、性能/发行未验，Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-018 → DEC-1160/1162 → 真实确认撤销 Owner → 本项目 GET/CREATE 负例 → 到期/修订直接负例 → Gate3/Release。
