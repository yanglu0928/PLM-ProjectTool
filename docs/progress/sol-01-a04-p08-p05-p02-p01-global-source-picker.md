# SOL-01-A04-P08-P05-P02-P01：GLOBAL 多来源只读候选选择

日期：2026-10-09；结果：`MULTISOURCE_READONLY_PICKER_CONTRACT_PASS`，仅前端合成合同与构建，不是多来源 Preview/Confirm 或实际人工核查通过。

编码前检查：Phase 2；输入 P05-P01 前置核查、CR-SOL-009/010、既有 GLOBAL Evidence List/Viewer/当前资格客户端。前置单来源 Win11 Edge/隔离 PG 链通过。本任务仅处理管理员构建有序候选集合，不动后端、Schema、冻结 API 或权限。验收为非管理员失败关闭、分页、固定版本身份/当前资格再核验、相同版本计一次、刷新清空以及不暴露写提交。

实现：新增 `/admin/reference-deidentification` 只读候选页及 GLOBAL Evidence 页入口。列表仅使用当前受权 GLOBAL Evidence API；候选必须显示 ELIGIBLE，加入时重取 Viewer 和当前资格，三个身份一致且现时仍 ELIGIBLE 才保存。按点击顺序保留 Evidence；同 DocumentVersion 首见去重计数，上限 500 条 Evidence/100 个不同版本。逐项显示 Viewer 的固定原文 URL，移出/重新读取会更新或清空候选。此页没有 Preview/Confirm/Revoke 或 AI 自动判断；服务端未来操作仍独立重验。

验证：新页面定向 3 项覆盖分页/顺序/文档去重、资格已撤回拒绝、非管理员不请求；前端全量 `106 files / 1628 tests`、typecheck/build 通过。未运行本项新增 Edge/PG 测试，未证明跨页网络竞态之外的真人核查；前序 P04-P03 单来源 Edge 证据不冒充多来源验收。既有主包 >500kB 警告。

兼容/升级/回滚：仅增量前端路由/链接，无 API/Schema/依赖/数据迁移。可移除新入口和页面回滚，不影响旧单来源确认及历史。风险为候选状态可能在选择后变化；下一项 Preview 前逐项重新读取，Confirm 继续以服务端现时来源指纹栅栏为准。P05-P02-P02 增集合 Preview/逐项打开/显式人工声明，P05-P03 再做 Win11 Edge/隔离 PG 多来源验收。实际人工确认、正式 License/目标账户、Server 2025、20 并发/Gate 3/发行未验；Debian 13 依用户指令跳过。

TraceLink：CR-SOL-009/010 → P04-P03 → P05-P01 → 本 P05-P02-P01 → P05-P02-P02/P05-P03。
