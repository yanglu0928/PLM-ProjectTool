# PLG-01-A02：插件包签名验证器编码前检查

- 日期：2026-11-03
- 状态：IMPLEMENTED / PASS_SCOPE_LIMITED
- Phase/WBS：Phase 2 / PLG-01-A02
- 上一项：PLG-01-A01 PASS_SCOPE_LIMITED（hosted run 41566771430）
- Change Request：CR-PLG-001（算法与消息格式先记录）
- 执行环境：GitHub hosted Windows Server 2025 runner；D盘runner temp；禁止用户本机/C盘执行

## 单一目标

提供 Plugin Owner 可消费的纯签名验证边界：对调用方提供的完整归档 bytes 计算 SHA-256，以固定 Ed25519 格式验证签名，并通过明确 Trust Port 解析可信签发者。只做纯验签，不导入/持久化包、不更改状态、不装载 Manifest、不执行插件、不暴露 HTTP。

## 编码前检查

|检查|证据与结论|
|---|---|
|正式基线|ADR-005要求插件加载前验证开发者签名，并明确客户仅安装开发者包、无强代码沙箱；DM-04定义不可变 package hash、manifest snapshot、signature/signer key ref、verification evidence；API-03导入仅接收开发者签名包。基线未指定算法或签名消息格式。|
|PoC 边界|POC-08当前用 `sha256:<entrypoint hash>` 校验单入口文件完整性，并在文档明确未证明开发者身份；不能作为生产签名验证复用。|
|Owner与模块|唯一 Owner 是 `modules/plugin`；不允许Output/其他业务模块自行做验签。保持领域/应用边界，不从插件包读取可信公钥。|
|依赖与存储|backend 已锁定 `cryptography==50.0.1`；A01表已保存签名、signer_key_ref、完整包SHA-256及验证摘要，无Schema变化需要。|
|算法/格式决策|CR-PLG-001预先记录 Ed25519 detached signature，签名消息由域分隔、2-byte key-ref长度、key-ref UTF-8和32-byte完整包SHA-256构成；公钥必须由受信 Resolver Port返回。签名为64 bytes、raw公钥32 bytes。任何格式改动须新版本/CR。|
|本项边界|新增独立 `PluginPackageSignatureVerifier` 与 `TrustedPluginSignerResolver` Port；失败关闭并返回非敏感结果。无生产Resolver适配器、无数据库写状态、无API/Migration/网络/Plugin进程。|
|验收标准|正向固定向量；包或签名篡改；错误签名长度；未知、禁用或撤销key；公钥类型/长度无效；key-ref编码/长度边界；无秘密/签名/包正文回显；定向、后端全量与wheel在hosted运行通过。|
|风险|验签只证明摘要由对应私钥签署；不证明代码安全。信任Port误接受包自带key会失去信任根。归档大小限制、Manifest/路径/兼容性检查、安装及强沙箱不属于本WBS。|
|回滚/迁移|无数据库/API迁移；失败时保持包导入关闭并移除未发布调用点。当前没有正式包/历史包搬迁；POC的hash字段必须拒绝作为签名身份。|
|Secret与数据|仅生成运行时临时Ed25519单测密钥；不得提交密钥材料、客户数据、完整包或运行日志。云端runner D盘结束自动清理。|

## 编码文件范围

预计新增 `modules/plugin/application/signature_verifier.py`、合成单测及对应进度文档。参考现有 License Owner 验签器的 application 层分层；Plugin 使用独立 Resolver/结果类型，不共享 License trust root；不改ORM、migration、API Contract、默认组合或运行行为。

## 约束

当前未提供正式发布者公钥/撤销信任源。因此仅通过注入的合成Resolver证明验签算法与拒绝边界，不得标记真实包 `VERIFIED`、不得宣称正式信任或可安装。实装生产信任源另立WBS。


## 云端验收结果（2026-11-03）

- 代码提交 `11a4e33448fc68718e43d8d7d3572ac2c703b6a8`；GitHub hosted run [41569062762](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41569062762) 全13 jobs success。
- 后端全量/wheel、前端、PG18、父包/A35/A17/A34通过；8项Plugin验签专项单测通过。
- 本项没有接入生产信任源，所有验签通过仅针对运行时合成密钥。
- 结果 `PASS_SCOPE_LIMITED`；下一项 `PLG-01-A03` 先核查并实现生产发布者公钥可信来源/撤销边界。
