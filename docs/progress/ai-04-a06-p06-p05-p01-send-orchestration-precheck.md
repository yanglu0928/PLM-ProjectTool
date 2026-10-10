# AI-04-A06-P06-P05-P01 发送编排与 SecretResolver 前置核查

日期：2026-10-03；状态：`PRECHECK_PASS_WITH_REQUIRED_SPLIT`；依据 CR-AI-017、DEC-745～749、P06-P02～P04。

静态核查确认P06-P03当前Claim只证明数据库检查瞬间Lease有效，`AITaskExecutionClaim`、Grant与SendProof没有携带`lease_expires_at`或数据库观察时间；P06-P04 Route允许最长120秒总网络时限。若直接把pre-send、SecretResolver和Adapter串接，调用可能在Lease剩余时间不足时开始，导致远端请求越过当前Jobs generation的租约截止。授权/License有效期不能替代Jobs租约边界。

现有`ProviderProbeSecretAccessAudit`也不能复用：它的ContextVar只接受`ProviderTestPreflightSnapshot`并固定Probe身份。业务AI Task需要以Task/Invocation/Job generation/Route/SecretVersion/原请求人为审计身份，保持Project追溯且不得伪装成Probe。

决定拆分：P02扩展内部AI Task Claim，携带数据库`observed_at`与精确`lease_expires_at`；pre-send只有在剩余Lease大于Route总超时加安全余量时才签发Proof，Proof的开始截止时间取Authorization与`lease_expires_at-total_timeout-margin`的较早值。P03新增AI Task专用Secret审计作用域。P04实现发送编排：第一次pre-send取得精确SecretVersion，`SecretResolver.use(expected_version_id=...)`后再次pre-send，要求Route/Grant/Invocation generation未漂移并立即调用Adapter；任何差异均在网络前失败关闭。

Changed/Files：仅本进度、CR/决策、状态和版本说明。Migration/API/Dependencies：无。Tests：静态检查Jobs lease/checkpoint、AI Claim/pre-send、SecretResolver/Store和Probe审计/Worker组合；本项无运行代码，不标发送PASS。Compatibility/Rollback：后续只增内部字段/Owner/编排，不改Schema或公开API；未装配前无行为变化。Known Issues：P02～P04尚未实现；真实Provider/客户数据外发仍未授权，响应Schema/终态、Windows Worker、Server2025/Gate3/UAT/可用包仍待。Next：`AI-04-A06-P06-P05-P02` Claim租约窗口与SendProof开始截止约束。
