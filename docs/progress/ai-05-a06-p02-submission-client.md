# AI-05-A06-P02 严格外发授权与 Task 提交客户端

日期：2026-10-03；状态：`AI_SUBMISSION_CLIENT_PASS`；依据冻结 API-03、AI Task Create V1增量、CR-AI-021与P01选项接口。下一项：`AI-05-A06-P03` 三步提交页面。

新增单一 `AISubmissionClient`，严格解析项目提交选项，并封装 Egress Preview、Authorize、Revoke 与 AI Task Create。写请求通过 `SessionClient` 私有CSRF桥接；每步要求调用方保留独立幂等键，Authorize/Revoke绑定强ETag。网络超时、非JSON、未知状态或响应身份不一致统一为不确定结果，客户端不自动重试、不自动换Key；已知安全错误只使用白名单code，不显示服务端message。

客户端只接受固定 `DOC-02` 版本引用、受控Policy refs和标量参数。Preview请求可选择服务器投影的Provider/Model，但Task Create只提交冻结字段和AuthorizationRef，不携带Provider、endpoint、API Key或Prompt正文。Authorize有效期不得晚于Preview过期时间；Revoke明确提示不能撤回已发送数据的语义留页面处理。

定向 `AISubmissionClient + SessionClient` 163项通过；前端全量66文件/1244项、typecheck及Vite 141模块构建通过。产物SHA-256：HTML `6191140d2b52ca02d407f2db6bb6140081ffc68693d4a2ee01eae5bfd5374e26`、JS `149da772b33b848fd008b1b7f4178a24702bcf70b2a39eaa769ec0ba969a706b`、CSS `db65985b4714d88dc1d693078d755f4264555e2bfe4450a69cf2eba93844ebca`。无后端、Schema、Migration、依赖或真实外发变化；删除客户端和Session桥接方法可回滚。
