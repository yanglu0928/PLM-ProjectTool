# SUR-01-A04-A02-P03：Survey Review HTTP 合同与生产组合前置

日期：2026-10-06。结论：`SUR_01_A04_A02_P03_REVIEW_HTTP_PASS`。下一项：`SUR-01-A04-A02-P04` Windows 写组合与真实 HTTP/PostgreSQL 链。

## 实施结果

- 复核确认冻结 PROJECT Review 的 create/start/decide/withdraw 四写 Router 已按 `subject_type` 调度业务 Owner，能够原样承载 `SRV-02`；本项不复制 Survey 专用 Review 路由，也不新增冻结外路径。
- 新增 Survey 合同测试，固定 `SRV-02 + SURVEY_ALL_V1` 的创建、强 ETag 开轮、批准终态和最小响应投影，并验证默认应用保持 404、受信 Origin/Session/CSRF/幂等、严格 JSON 白名单及冻结错误码。
- HTTP 层只构造通用 Review 命令，不读取或写入 Survey 私表；Survey 当前事实、状态绑定与正式化继续由已验证 Subject Owner 在调用方事务内负责。

## 生产组合前置结论

下一项可复用现有 Windows runtime/UOW、Session、License、Audit、Project Reviewer、Review 三仓储，以及 Survey 的四类来源证明和 `SurveyReviewSubjectOwner`。必须建立单一 Survey Review composition，只在显式平台写模式注入；默认、login-only 与只读组合继续关闭。P04 前不得宣称真实 HTTP/PostgreSQL 链已通过。

## 验证与回滚

- 新增 Survey HTTP 合同 3 项；连同通用 Review 合同和 Subject Owner 定向共 13 项通过。
- 后端全量 2810 项通过、3 项既有条件跳过。首次从仓库根执行 discovery 在中文 Windows 路径下于收集前失败；切到既有测试包目录并显式设置仓库根/源码路径后完整重跑通过，产品代码未改变。
- 开发 wheel 1038 项并包含 Survey Owner，SHA-256 `bc9bd853a438bdd3b2e63b6fff76e15b4bed53954b99bd7bd47a911ff15cbc7d`。
- 无 Migration、ORM、运行时代码、公开路径、依赖、Secret、网络或数据外发变化。移除本项合同测试不影响运行系统；生产入口仍默认关闭。Windows Server 2025/Debian 13、业务提交捷径、读取/UI、Round/Response/Conclusion、Gate 3/UAT/发行仍待。
