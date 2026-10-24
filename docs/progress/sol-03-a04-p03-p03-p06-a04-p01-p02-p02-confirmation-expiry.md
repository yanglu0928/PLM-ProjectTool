# SOL-03-A04-P03-P03-P06-A04-P01-P02-P02：确认到期精确边界直接拒绝

日期：2026-10-09。结果：Win11 可弃 PostgreSQL 18.6/真实项目 HTTP 的受控时钟边界测试通过；正式可信时间密钥/服务账户未验。

## 编码前检查

- Phase/WBS：Phase 2 Platform Core / 本项；输入 Gate2 API-04、CR-SOL-018、DEC-1160/1163、已验撤销负例及 `ReferenceUseProofService` 时钟端口。
- 单一问题：最新确认尚未撤销且所有来源、成员资格有效时，项目候选/CREATE 是否在 `expires_at` 精确边界立即失效。
- 模块/实体/API/权限：仅新增验证脚本；复用生产 PG Repository、Project Owner、候选与 CREATE API，测试组合仅注入证明服务时钟；不改数据库、生产 API、角色或依赖。
- 验收：时钟设为 `expires_at-1µs` 候选可见；设为 `expires_at` 候选隐藏，原固定引用 CREATE 拒绝且无版本/创建 Audit/收据；上游真实来源夹具可继续全部自测并清理可弃 PG。
- 风险：等待一天不实际，修改确认历史会破坏封闭账本。使用应用现有时钟注入点，只改变测试组合的瞬时判定，不修改 `expires_at`、绕过 Guard 或把结果描述成正式可信时间验收。

## 验证

新增 `validation/sol-03-a04-p03-p03-p06-a04-p01-p02-p02-confirmation-expiry/verify.py`。在真实未撤销确认、PG 文档/证据和有效项目 PM 上，分别以 `expires_at-1µs` 与 `expires_at` 构造证明服务；前者项目 GET 200 返回候选，后者 GET 200 空项，OutlineVersion CREATE 503。SQL 确认 0 个该目录版本、0 个创建 Audit、0 个创建收据。脚本首轮以到期后 1µs 通过，改为精确边界/边界前对照后重跑退出码 0，输出 `GLOBAL_CANDIDATE_CONFIRMATION_EXPIRY_PASS`；上游真实来源夹具随后正常完成。该证据覆盖服务时间判定，不证明正式可信时间来源的安装与恢复。

兼容/升级/回滚：只增验证资产，应用代码/Schema/Migration/API/权限/依赖不变；移除脚本即可回滚，历史保留。下一项 P01-P03 验证 GLOBAL 当前版本修订使旧发布候选/旧固定引用失效；CR-SOL-018/Gate3 不关闭。正式服务账户、Server2025、性能/发行未验；Debian13 实机依用户指令跳过。

TraceLink：Gate2 API-04 → CR-SOL-018 → DEC-1160/1163 → 确认账本期限 → 项目候选/CREATE 直接边界 → 版本修订 → Gate3/Release。
