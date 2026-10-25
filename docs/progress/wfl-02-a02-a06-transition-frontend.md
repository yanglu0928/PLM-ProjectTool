# WFL-02-A02-A06：Stage Transition安全前端客户端与显式确认页

日期：2026-10-06
状态：`WFL_02_A02_A06_TRANSITION_FRONTEND_PASS`

## 实现

- `SessionClient`新增单次同源Transition传输，只持有私有CSRF并传原Key/强ETag；超时或网络未知不自动重试。
- 严格业务客户端固定`HANDOVER -> SURVEY`，要求当前Workflow为ACTIVE、HANDOVER为ACTIVE、
  两项展示快照均PASS；只发送规范理由和空`gate_snapshot_refs`，白名单核对最小回执、版本+1、
  项目/Workflow/理由/强ETag并把首次历史标记为非当前状态证明。
- Workflow页只对ProjectManager显示推进；理由与二次确认必填，不提供内部UUID输入或输出。
  未知结果把actor/project/workflow/Key/ETag/理由/目标保存到当前Session，独立GET仍为同版本且
  前置仍满足时才允许原样重试；版本变化只允许人工核对审计后清除记录。

无后端、Schema/Migration、冻结API、角色、依赖、Secret或外发变化。删除新增客户端、Session
桥和页面区块可回滚；后端生产组合与历史不变。

## 验证

- Session桥、严格客户端和页面定向`195`项通过，覆盖安全输入、响应白名单、错误映射、
  双PASS显隐、明确理由、UUID零展示、未知写保留/同Key重试及畸形存储失败关闭。
- 前端全量`78`个文件、`1395`项通过；`vue-tsc`/`tsc`通过。
- Vite生产构建`164`模块通过；主JS `599.03 kB`、gzip `149.67 kB`，保留既有大于500kB
  分块警告，不将性能建议误报为构建失败。
- 首轮定向验证发现两条旧提示断言因扩展文案失配、重试夹具复用已消费Response，以及严格
  解析器一个TypeScript收窄问题；修正提示兼容、每次生成Response并显式收窄后完整重跑通过。

本项不代表真实浏览器/网络/数据库、其余阶段Owner、WAIVED、性能、正式信任、Gate 3、UAT或
发行通过。下一项`WFL-02-A02-A07`以Windows 11真实Edge、构建Vue、生产FastAPI和PostgreSQL
18.6验证用户点击、首次Transition回执、独立当前态刷新及唯一历史/Audit/receipt。
