# AI-04-A06-P06-P05-P04 Provider 发送顺序编排

日期：2026-10-03；状态：`INTERNAL_PASS`；依据 CR-AI-017、DEC-749～752、P05-P02/P03。

新增内部 `AITaskProviderSendService.send_once`，把可执行顺序收敛为唯一调用：首次 post-Begin pre-send → 绑定 Task Secret 审计与业务 trace → SecretResolver 按首次 Route 精确 SecretVersion 读取/解密/审计 → 第二次 post-Begin pre-send → Route 完全一致且 SendProof 除最新开始截止外身份/摘要完全一致 → 立即调用 ProviderAdapter。第二次授权重验仍覆盖当前 Lease/Fencing、Task/Invocation、Authorization、Provider/Config/Model/SecretVersion 和 License；Adapter 还会在网络前复核最终 proof/envelope。

Secret 轮换、授权/租约/License变化、Route/Invocation/Job generation/payload 漂移、审计失败、Secret失败或错误 Adapter 返回均失败关闭；进入 Adapter 后的固定安全错误码保留给后续终态分类。密钥只在 SecretResolver 上下文中存在并在任意退出路径清零，响应作为 owned `AIProviderResponse` 交给 P07，错误类型返回则拒绝。该服务名为 send_once 只表示一次方法调用最多调用一次 Adapter，不声称跨进程崩溃或网络超时下远端 exactly-once；P07/P08必须以持久终态/UNKNOWN/对账关闭此风险。

验证：新单元 4 项/5 子用例，相关定向 **17 项/23 子用例**；Windows 11/PostgreSQL 18.6 真实 Claim→Envelope→Begin 链上使用真实 pre-send、PostgreSQL Secret Store、真实 Project Audit、合成解密器和合成 Adapter，证明两次授权、精确当前 SecretVersion、一次 Adapter 调用及密钥/响应清零；零真实 Secret、零 Provider 网络。后端全量 **2235 项通过、3 项既有条件跳过、2912 子用例、无失败**；开发 wheel SHA-256 `98575f61b942d999a86771d8e76ec6d40e64821eb784bc2462abd210dde38de7`。

Changed/Files：发送编排应用服务、单元、PG组合验证，并为P06-P03验证器增加默认关闭的pre-send service验证注入。Migration/API/Dependencies：无。Compatibility/Rollback：未装配内部增量；停止业务AI消费并撤服务即可，Schema、冻结API、固定Probe和历史不变。Known Issues：响应正文Schema/Suggestion Owner、Invocation成功/失败/UNKNOWN终态、持久化防重/崩溃对账、Windows Worker、Server 2025、Gate 3/UAT/可用程序包仍待；真实Provider/客户数据调用未在本项执行。Next：`AI-04-A06-P07-P01` Provider响应Schema、Suggestion与Invocation终态前置核查。
