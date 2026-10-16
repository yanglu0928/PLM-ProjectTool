# HND-01-A04-A02-P03：Review HTTP 合同与生产组合前置

日期：2026-10-05。结论：`HND_01_A04_A02_P03_REVIEW_HTTP_PASS`。下一项：`HND-01-A04-A02-P04` Windows写组合与真实HTTP/PostgreSQL链。

## 实施结果

- 新增默认关闭的PROJECT Review四写端点Router，直接调用已验证的create/start/decide/withdraw应用服务，不在HTTP层跨Owner写业务表。
- 实现受信Origin、Session/CSRF、幂等键、严格JSON、规范UUID、开轮/撤回强If-Match、决定枚举及RETURN实质comment边界。
- 增加API-02已冻结的`REVIEW_SUBJECT_LOCKED`、`REVIEW_REVIEWER_INELIGIBLE`、`REVIEW_COMMENT_REQUIRED`、`REVIEW_DECISION_EXISTS`统一安全错误投影。
- 细化成功响应的最小白名单，只回传身份、固定版本、状态、ETag和时间；不返回主题正文、来源内容、Owner名或内部异常。

## 生产组合前置结论

现有Windows composition已提供共享runtime/UOW、Session、License、Audit及Handover/Review所需仓储，无新Schema、Secret、配置或第三方依赖前置。P04必须创建单一Windows Review composition，仅注册`HND-02` Owner并仅在`--platform-write`注入；默认、login-only和只读Platform保持不可写。本项不宣称生产组合或真实HTTP/PG PASS。

## 验证与回滚

- Review HTTP合同5项通过；Review相关定向109项通过；后端全量2672项通过、3项条件跳过。
- 默认app 404；显式Router的创建/开轮/批准/撤回成功投影、强ETag、安全门禁和冻结错误码通过。
- 开发wheel构建并直接导入Review Router通过，SHA-256 `f5693a3fce3237f24516cb5f80bf354a3d9b01379dea52d3e99218c6550dbf64`。
- 无Migration、依赖、配置、网络或数据外发。撤销Router注入参数可恢复默认404，内部Owner与历史数据不受影响。
