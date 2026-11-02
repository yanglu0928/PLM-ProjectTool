# PLT-PKG-01-A09-P51-A50：待办到原文位置的最小跳转审计（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成；选定兼容只读子资源，实施前差异已记录在 `CR-HND-009`。
- 当前Phase：Phase 2 Platform Core，Gate 3 BLOCKED
- 当前WBS：PLT-PKG-01-A09-P51-A50
- 输入基线：冻结 API V1/DM-05、HND Action GET/List read、Survey source-location increment、Evidence Viewer contract、`CR-HND-009`
- 前置任务：HND-01-A06-A04 Action 只读工作台、HND-02-A04-A02/A03/A04 Action read owner/HTTP/Windows组合、SUR-01-A06-A04/A05 Survey source location、DocumentVersion authorized download 与 Evidence Viewer 已有
- 涉及模块：Handover Action read frontend/backend、Handover detail view、Project authorization、Document/Evidence 只读导航
- 涉及实体：Handover Action、不可变 HandoverAnalysisVersion、HandoverAnalysisItem、Project
- 涉及API：现有 `HND_ACTION_GET` 不变；新增可选只读 `GET /api/v1/projects/{project_id}/handover-action-items/{action_item_id}/source-location`
- 涉及权限：与 `HND_ACTION_GET` 相同的 Session、License、当前 Project 成员授权；服务器从 Action 固定版本/问题引用解析，目标详情再独立重验。跨项目/不存在/越权隐藏为404
- 验收标准：同项目 Analysis Action 可跳至固定版本和准确问题卡片；HUMAN来源不给伪造路径；跨项目/失效/不一致/恶意响应失败关闭；Evidence Viewer仍重新授权且内容保持在固定DocumentVersion；定位失败保留Action详情及待编辑状态；Windows Edge在hosted运行器合成验证
- 风险：现有 Action Detail 仅包含版本ID+问题ID，缺少父 Analysis ID；不能安全拼接既有详情路由，也不可通过遍历所有分析推算。现有 Survey SourceLocation 和 Handover Evidence Viewer已提供固定版本/Project授权模式，可复用安全原则但不是 Action→Analysis 导航的现成端点。
- 回滚：移除可选子路由、客户端和前端按钮/query参数；无数据库或历史业务数据迁移。

## 目标与核查证据

落实用户偏好：待办可点击定位原文/精确业务问题，不复制长正文到表格。调研业务表单只是参考，实际项目记录优先。

- `HandoverActionReadClient`严格校验当前 Action Detail，已有`source_analysis_version_ref`和`source_item_id`，但没有`handover_analysis_id`。
- `ProjectHandoverActionView`已有按需Evidence Viewer，按钮点击后按当前Project重新调用受权Viewer；Analysis Action来源当前仅显示ID/人工来源，缺少跳转。
- `ProjectHandoverDetailView`有固定 `fixedVersionId` 选择，但路由同时要求父 `analysisId`；问题卡片已有稳定 `analysis_item_id`。目标详情会对Project/Analysis/Version重新授权。
- Survey已有单独兼容来源定位 Operation；Evidence Viewer路径仅返回固定版本、安全 typed locator 与受权内容 URL。均不暴露本地绝对路径、正文下载捷径或内部row ID。
- DM-03要求Evidence绑定不可变DocumentVersion + typed locator；所有访问重新执行Scope/Project授权；不可信绝对路径及跨Project定位必须失败关闭。

## 选择与差异

根据 `CR-HND-009`，选择方案2：增加Action来源定位只读子资源，保持冻结Action GET JSON、现有29个冻结Operation与DB Schema/Migration不变。Operation只接受Project + Action ID，服务端使用当前Action记录关联的 Version/Item查父Analysis ID；HUMAN返回受控UNAVAILABLE。UI使用响应构造应用内部route，不接受来源API返回任意URL。目标详情利用固定版本GET验证并通过Item ID精准定位；Evidence仍由既有Viewer核验具体原文位置。普通默认应用不挂载新HTTP，只有显式Action Read组合提供。

备选方案1（改旧Detail投影）会扩展冻结响应shape并让旧严格客户端失败，未选；方案3仅显示ID无法满足需求，未选。无Schema/迁移、依赖、配置、AI/客户数据发送或外部服务变化。

## 云端验收/边界

使用合成Project/Action/Analysis/Version/Item/Document/Evidence。hosted Windows runner：后端Owner/API/显式Windows只读组合、跨Project/不存在/HUMAN/关系不一致；前端Client/View精确导航、越权/异常保持状态、分页/失效目标；Vite typecheck/build及Edge packaged/browser。仅本机零代码运行；无客户资料外发；不测试正式信任/生产服务，不推定Windows11设备、Gate、Pilot或Release通过。


## 实施结果（2026-11-02）

- 状态：PASS_LIMITED；代码与全量自动化验证通过，来源导航专项 hosted Edge 验收待 A50-E01。
- 后端：新增只读 source-location 子资源和同权限 Owner/项目范围来源解析；HUMAN来源受控不可用，既有Action GET及Schema/Migration不变。
- 前端：新增严格同源响应客户端和“打开原始问题与证据位置”入口；只有服务端解析到的固定来源才构造内部路由，详情按固定版本分页到准确问题卡并滚动定位。
- hosted run [41391544470](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41391544470) 全12 jobs成功：后端3,850项，前端2,075项/200文件，类型检查/生产构建通过；父包、A34、PG18.6/pgvector0.8.6和A17 PlanVersion Edge/HTTPS/PG通过。
- 首轮 run 41391080344 暴露既有Windows组合根测试仍断言2条路由；偏差先记于 CR-HND-009，再更新清单，复验全绿。
- 限制：run内A17 Edge只验证PlanVersion，未验证A50的Action入口、HUMAN/失效响应与精准锚点浏览器路径；不据此宣称A50专项Edge通过或Windows11设备/Gate/Pilot/Release通过。
- 环境：GitHub Hosted Windows Server 2025 runner，仓库与临时数据在D盘；未在用户本机或C盘运行项目程序。无产品服务/API正式启动、无客户资料外发。
- 下一项：`PLT-PKG-01-A09-P51-A50-E01` hosted Windows Edge合成待办来源导航端到端验收。
