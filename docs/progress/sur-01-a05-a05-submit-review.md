# SUR-01-A05-A05：SurveyVersion 原子送审

日期：2026-10-06。结论：`SUR_01_A05_A05_SUBMIT_REVIEW_PASS`。下一项：`SUR-01-A05-A06` Survey 四读 HTTP 与签名 cursor。

## 编码前检查与范围

冻结 API-04 要求业务 `SUBMIT_REVIEW` 一次完成创建 Review 和开始首轮；A04 已验证 `SRV-02 + SURVEY_ALL_V1` Subject Owner 与通用 PROJECT Review 内核。本项新增 Survey 业务编排 Service、默认关闭的严格 HTTP Router、ProjectManager 授权策略和显式 `create_app` 注入点，不复制 Review 私表写入，不进入 Windows 生产组合。

冻结请求中的 `due_at`/`submission_note` 在现有 Review Schema 无持久化位置，已按持续授权建立 CR-SUR-005：V1 保留字段但只接受 null，非空 422，避免静默丢数据或在本项跨模块扩 Schema。

## 实施与验证

Service 在一个 Owner 事务内完成 Session/CSRF、双 License、ProjectManager、评审人、Subject 当前事实、Review 创建/首轮、SurveyVersion 状态、Audit 与持久幂等回执；评审人排序进入指纹，同键重放恢复首次 Round 并重新检查 Subject 访问，死锁有界重试三次。

- 定向19项通过：原子调用、规范排序、持久回执、首次结果重放、Owner重验、License与输入负例、默认关闭、严格DTO、安全边界和错误投影。
- Windows 11/PostgreSQL 18.6 真实链通过：Audit失败全回滚；HTTP原子送审与同键重放；来源漂移拒批、恢复批准；批准后重放首次结果；第二版本送审后撤回；Alembic无新操作。标记 `SUR_01_A05_A05_SUBMIT_REVIEW_PASS`。
- 后端全量2838项通过、3项跳过。
- wheel 含新增 Application/API 与组合入口，共1049 entries；SHA-256 `170083bd760238bff4948b3a9bed3613d523d18dfd991030de4c4aed4917a3b7`。

## 兼容、回滚与未完成

无 Schema/Migration、ORM、依赖、配置、Secret、网络或外发变化；Schema head 保持0106。默认入口404，停止注入 Router 可回滚，合法业务历史不删除。

A06四读HTTP/cursor、A07 Windows生产组合、Survey UI、Round/Response/Conclusion、Server 2025当前链、Gate 3、UAT和发行仍按总状态跟踪；Debian 13实机按用户指令跳过，不冒充已验证。
