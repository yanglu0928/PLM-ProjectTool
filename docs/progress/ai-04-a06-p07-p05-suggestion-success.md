# AI-04-A06-P07-P05 Suggestion 成功结果原子发布

日期：2026-10-03；状态：`SUGGESTION_SUCCESS_PASS`；依据 CR-AI-018、DEC-754～757、Schema0074、P07-P02～P04。

新增成功结果发布服务与PostgreSQL Repository。Provider响应经受信Schema解析后，发布事务先以当前Job Lease/fencing终结Job/Attempt/Lease，再从不可变Content Plan把模型引用的授权来源序号解析为真实Owner/Object/Version/内容指纹；随后写不可变`NOT_FORMAL_FACT` SuggestionPayload/Evidence，更新Invocation为`SUCCEEDED/VALID`并绑定真实Payload，更新Task为`SUCCEEDED/AVAILABLE`，追加Project Audit，最后一次提交。模型不能提供证据身份或直接写正式业务表。

Provider成功编排始终在返回或异常路径清零Response；Key仍由既有发送编排清零。解析、Evidence、Jobs、Schema/FK、Audit或SYSTEM actor任一步失败时，Job终态和全部结果写入同事务回滚，Invocation保留RUNNING供P08安全收敛，不回退PENDING、不重新发送。

Windows 11/PostgreSQL 18.6真实Claim/Plan/Invocation/Secret/Audit链配合单次合成Adapter验证：注入Audit失败后Job/Suggestion/Invocation/Task全部回滚；同一未重发响应随后原子提交Payload/Evidence、Invocation、Task、Job/Attempt/Lease和Audit，Evidence指纹与Content Plan一致，响应/Key清零。新增3项单元/2子用例，后端全量 **2248项通过、3项既有条件跳过、2922子用例、无失败**；开发wheel SHA-256 `a1a3f0f3e6b3b4167f7ff395810b8a4ca5216d6c325758831db08ddb3c8b0b79`。无Schema/API/依赖/真实Provider外发；下一项P08实现失败、UNKNOWN、取消、对账和显式Retry。
