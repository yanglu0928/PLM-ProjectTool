# WFL-02-A02-A04：冻结 Transition HTTP 兼容投影与严格边界

日期：2026-10-06。结论：`WFL_02_A02_A04_TRANSITION_HTTP_PASS`。
本项关闭默认关闭的HTTP合同，不代表Windows生产组合、真实HTTP/PG、前端、Gate 3或发行通过。

## 编码前检查与偏差

冻结`WORKFLOW_TRANSITION`固定POST路径、ProjectManager、S/L/C/I/M/A和200结果，但
`gate_snapshot_refs`未定义元素Shape或可信语义。实施前建立`CR-WFL-009`，按用户持续授权
采用兼容方案：三个字段仍全部必填，当前V1只接受空数组并由服务端权威重证/固化Gate；
不猜造客户端UUID DTO、不修改冻结提交`64cdf09`。

## 实施结果

- 新增显式注入的`POST /api/v1/projects/{project_id}/workflow:transition`，默认应用保持404；
  应用工厂只增加可选Router插槽，尚未接Windows生产组合。
- 强制可信Origin、唯一Session/CSRF、持久幂等键、强If-Match、无query、单一JSON
  Content-Type、2MiB上限、UTF-8、重复键/非标准常量、exact fields及canonical Project UUID。
- 请求精确为`target_stage_key`、`reason`、`gate_snapshot_refs`；后者必须是空数组。目标/理由
  的业务限制继续由A03验证，HTTP不信任客户端Gate事实。
- 200仅返回Transition/Workflow/Project身份、定义版本、来源/目标、发生前后版本、当前版本、
  理由、UTC时间和强ETag；不返回Gate内部摘要、Owner锁、路径、正文或AI内容，响应`no-store`。
- 注册冻结`WORKFLOW_TRANSITION_INVALID` 409并安全映射身份、License、版本、幂等、Gate及
  状态错误；服务违约、外部异常和不一致结果统一503且不泄露内部信息。
- 无Schema/Migration、依赖、Secret、外发或客户数据变化。回滚为撤Router注入/应用插槽，
  A03服务和既有历史保留。

## 客观验证

- 合同4项覆盖默认404、精确成功投影/ETag/no-store、Session/CSRF/Origin/Key/If-Match、
  query/未知缺失重复字段、非空/错误类型snapshot refs、canonical UUID及完整安全错误映射。
- 首轮定向验证发现两项测试/注册偏差：测试试图构造领域不允许的非相邻结果，以及冻结
  `WORKFLOW_TRANSITION_INVALID`尚未进入运行错误表；删除无效夹具、补冻结错误注册后重跑通过。
- 最终后端`2777`项通过、`3`项既有条件跳过；开发wheel`1013`项包含新HTTP模块，
  SHA-256 `84694eb7f938d3b597dd909a612bff6062a617c6e8559fc12b7c817f5facf158`。

下一项`WFL-02-A02-A05`将Router装入Windows显式写组合，并以真实Session/Handover Owner、
两项Checklist PASS、PostgreSQL Transition/Audit/receipt验证HTTP闭环；默认/登录/只读模式继续关闭。
