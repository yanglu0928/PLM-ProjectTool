# CR-SUR-013：已批准交接问题的调研固定来源发现入口

日期：2026-10-25。状态：`SUR-07-A05` Windows 11/隔离 PG 验收通过，
后续前端选择器/包内链待验。关联
`CR-EXEC-002`、`CR-SUR-002`、`SUR-07-A04`、Gate 2 原冻结提交 `64cdf09`。

## 来源与冲突

Windows 11 非发行包已验证交接版本批准、两张问题 `CONFIRMED`、调研定义创建。
首个 SurveyVersion 写合同却要求 `HANDOVER_ITEM` 来源携带
`handover_item_row_id + handover_analysis_version_id + handover_analysis_id`。
交接 `HND_VERSION_ITEM_LIST` 只公开稳定 `analysis_item_id`；版本写入时另生成
`analysis_item_row_id`，两者是不同 UUID，现有 `/api/v1` 无受权方式取得后者。
`CR-SUR-002` 的只读 Port 是服务端内部证明，不是用户来源选择操作。

让浏览器猜测 UUID、直接访问业务私表、把 `MANUAL` 来源标成已批准交接引用，
或向冻结的交接 GET DTO 静默加入内部字段，都不能满足当前合同和追溯要求。
业务表单只能作参考，实际访谈记录仍须由人工形成；本 CR 不自动确认客户事实。

## 选择与兼容

- 新增独立、只读、默认关闭的 `/api/v1` PROJECT 来源候选操作，供当前
  `PROJECT_MANAGER/IMPLEMENTATION_MEMBER` 在创建调研版本前选择。只返回
  当前项目 ACTIVE 分析、当前 APPROVED 版本中 `CONFIRMED/RESOLVED/ACCEPTED_RISK`
  问题的最小定位信息：固定行来源 ID、分析/版本/业务问题 ID、简短标题/状态。
  不返回文档/Evidence 正文、路径、AI 输入输出或其他项目资料。
- 浏览器取得候选 ID 不等于写权限。`SURVEY_VERSION_CREATE` 的现有 Owner
  在同一写事务内继续重证当前批准指针、问题状态和项目归属；来源在选择后变化
  则失败关闭，不自动降级为 `MANUAL`。
- 保留原 `HND_VERSION_ITEM_LIST`、SurveyVersion POST 路径/请求/响应及 Gate 2
  冻结版本，不增加旧响应字段，不改变既有客户端解析。新 GET/DTO/权限作为
  兼容增量单列 API Contract 和 OpenAPI/文档；不新增公开写操作。
- 列表使用服务器签名 cursor、稳定排序、页大小上限及防跨项目/用途混用；
  无匹配项返回空列表，不回退到未批准、历史非当前或其他项目版本。

## 偏差、风险、迁移与回滚

相对冻结 API：增加只读来源发现 Operation/DTO 和项目读权限；旧 Operation 不变。
无数据库 Schema/Migration、License 授权粒度、外部依赖或客户数据外发。
风险是固定行 ID 或问题标题泄露、伪造/陈旧 cursor、选择后撤权及误用历史来源；
通过当前 Session/License/项目角色与精确 ProjectId、Owner 当前事实、
`no-store`、分页签名和双阶段重证关闭。回滚可停止挂载新 GET 与前端选择器，
已有合法 SurveyVersion/Review/Audit 历史保留，不删除或改写。

## 验证计划与拆分

1. `SUR-07-A04`：冻结差距核查、本 CR 和前置条件；不实现接口。
2. `SUR-07-A05`：来源发现只读 Owner/DTO/新路由/Windows 显式组合及 API 增量；
   定向与完整后端回归、真实 PG/HTTP 当前/撤权/跨项目/未批准/历史/分页负例。
3. `SUR-07-A06`：严格前端来源候选客户端和调研版本创建客户端；验证来源组合、
   Session/CSRF/If-Match/幂等原号及结果未知处理。
4. `SUR-07-A07`：受权页面选择来源、目标部门与人工问题卡片，强调访谈优先；
   无固定来源时可明确写 `MANUAL`，但绝不伪称交接固定引用。
5. `SUR-07-A08`：从干净提交重建非发行包，真实 Edge/HTTPS/PG 验当前交接
   问题→Survey DRAFT 版本及 Audit/收据/拒绝/临时清理；不称真人确认或 Pilot/Gate。

任何实现若证明上述只读 DTO 不足或必须修改冻结写合同，应先修订本 CR、保留
本版记录，再按持续授权执行迁移/兼容验证，不静默扩权。

## SUR-07-A05 实施结果

独立 GET/最小投影、当前批准过滤、窄角色、用途隔离签名 cursor 与 Windows
显式组合已实现；原交接 GET/SurveyVersion POST 未改。为减少新的目标账户 Vault
供给前置，新用途族复用交接 Item cursor 已有 32 字节密钥，但 `family`、
Project/Session/页长严格绑定，交叉解码拒绝；不把这个复用称为新独立密钥。
定向/完整后端及一次性 PG18/HTTP 检验见进度记录。正式发行公钥、包内页面、
Server 2025/Debian 13 和真人确认仍待，Pilot/Gate/Release 未关闭。
