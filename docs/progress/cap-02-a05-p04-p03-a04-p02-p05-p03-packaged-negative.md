# CAP-02-A05-P04-P03-A04-P02-P05-P03：固定候选包内身份/游标/重放拒绝

日期：2026-10-24；结果：`WINDOWS_11_SYNTHETIC_PACKAGED_NEGATIVE_PASS / LICENSE_EXPIRY_PENDING / PILOT_NOT_READY`。

|编码前检查|结论|
|---|---|
|Phase/WBS|Phase 2 / `P05-P03`；只补同一固定非发行候选的 Review 拒绝及原号恢复矩阵，不修改产品。|
|输入基线|`CR-CAP-005/006`、`DEC-20261024-CAP-P05-P03`；候选 SHA `f2a2385538b111a1a36e3761086e0f4e5749554a3c57bde8941c0fb11080e095`、P05-P02 包内正向链。|
|前置|前片合成双条目/双评审批准及 Audit 通过；本片复用只读清洁暂存，另建全新双布局。|
|涉及模块/实体/API|仅验收脚本显式开关与薄入口；产品 ORM/Migration/API/权限均不改。|
|权限与验收|已登录未分配用户决定 404；当前受分配者在停用后固定内容不可见；签名游标跨两名当前受分配者会话返回 400；终态原幂等号重放返回首次回执，异号重试被拒且 Audit/决定数不增加。|
|风险|License 自然到期/撤销、正式可信时间与生产密钥未纳入此矩阵；不以包内普通未许可 Project 403 代替 Review 失效许可证明。|

在同一固定 ZIP/22,196 件载荷上复跑完整包内 PG/API/Caddy/HTTPS/Edge 来源、Evidence、双条目版本和评审链。未分配账号对决定 POST 得 404；Reviewer Two 签名游标不能由 Reviewer One 会话复用（400）；Reviewer One 临时停用后固定内容 GET 得拒绝，恢复后真实 Edge 登录/决定正常。Reviewer Two 最终批准后同一 Key 重放返回逐字段相同回执，不同 Key 再提交被 409/422 合同拒绝；PG 最终仍每人恰一条 `APPROVE`、Audit 共 2，当前批准版本指针唯一。脚本输出 `CAP_02_P05_P03_PACKAGED_NEGATIVE_PASS`，退出0；候选 SHA 前后不变，48 个合成 Vault 目标及两份临时布局、PG/API/Caddy/Edge 进程均清理。

本片的不同 Key 非法终态已通过拒绝，但具体 409/422 之一未在夹具中固定为单一码；冻结 API 对应实现的精确错误码仍应由合同测试保证。正式 License 到期/撤销、网络中断后客户端 UI 原号恢复、真人确认、正式信任/法律/离线安装升级、Server2025/Debian13、完整 UAT/Gate/Pilot/Release 未由本项通过。为尽快完成用户可操作的能力版本流程，下一项回到 `CAP-02-A05-P03-P02` 多条目编辑与 DEPRECATED 读写合同差异；License 失效包内负例保留 `P05-P04` 独立验收。
