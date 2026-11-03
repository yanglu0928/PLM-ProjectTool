# CR-PLG-001：冻结插件签名验证算法与消息格式

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / PASS_SCOPE_LIMITED
- 适用 WBS：PLG-01-A02
- 依据：ADR-005、Gate 2 冻结的 DM-04/API-03/SC-01～03、用户 2026-09-24 持续自主执行授权
- 原基线：开发者工作台为插件包签名；加载前验签。V1 只接受开发者包，不开放客户 SDK、任意第三方或插件市场。冻结基线未规定插件签名算法/消息格式。POC-08 的 `sha256:<entry-point-hash>` 仅是入口文件完整性检查，不提供开发者身份信任。

## 问题与变更

为实现可互操作且可失败关闭的生产验签，签名算法和签名消息必须确定。静默复用POC字段会把哈希完整性误称为签名信任。

本CR批准以下受限设计，不改写原冻结文档或提交 `64cdf09`：

1. 插件包采用 Ed25519 detached signature；只接受标准 64-byte signature 和 32-byte raw Ed25519 public key。
2. 对完整、准确的 package archive bytes 计算 SHA-256。签名消息固定为 domain separator `PLM-PLUGIN-PACKAGE\\0v1\\0`、2-byte unsigned big-endian key-ref UTF-8 byte length、完整 key-ref UTF-8 bytes、32-byte package digest 的直接拼接。签名覆盖包整体及 signer key reference；不从包内读取/信任公钥。
3. 验签器只经 `TrustedPluginSignerResolver` Port 解析外部受信公钥及状态。未知、撤销、非活动、格式错误或验签失败一律拒绝。测试夹具仅用临时合成密钥；正式 trust source/密钥仪式另立任务。
4. 私钥仅在独立 Developer Workbench；客户仓库、运行数据库、插件包和日志不保存私钥。不得把签名信任宣传为恶意代码沙箱。

## 影响与兼容性

- 本切片仅增加应用层纯验签服务/Port和合成单测；不新增ORM、Alembic、API、HTTP、网络调用或线上信任源。现有签名/摘要列足以保存 detached signature、signer ref 与完整包SHA-256。
- 现有POC-08 SHA-256 manifest signature不符合本格式，不作为签名开发者包接受。生产 PLG 表目前没有合法的已签名客户包；若发现此假设不成立，先暂停写入并在CR中记录数据兼容方案。
- Ed25519 使用已锁定生产依赖 `cryptography==50.0.1`；无需新增依赖。
- 对业务、Scope、公开API及数据库无迁移影响。算法固定后如需改变，新增版本化格式/CR，禁止同版本静默解释。

## 风险

- Ed25519证明持有对应私钥，不证明代码安全；ADR-005仍不提供强沙箱。
- Port 若错误信任包自带公钥/任意路径，攻击者仍可自签；正式 adapter 必须绑定工作台导出的信任锚和可审计撤销状态。
- 验签器只证明被签名归档字节一致；Manifest语义、路径安全、OS/API兼容、依赖策略、导入大小限制和执行隔离仍须独立校验。
- Python与开发工具对签名消息字节必须完全一致；域分隔、长度前缀与测试向量用于防歧义。

## 回滚与迁移

- 无数据库迁移、无数据回写。若实现/云端验收失败，保持插件导入与验签入口关闭，移除未发布的验签器调用并保留CR/失败证据；不接受POC签名冒充开发者签名。
- 该机制没有正式导入包或已签名业务数据，因此不存在历史包重新签发/数据搬迁。

## 验证计划

- 正向：真实 Ed25519 synthetic key 对相同完整包和 key-ref 的固定向量验签通过。
- 负向：包单字节篡改、签名篡改/长度错误、未知或撤销 key-ref、公钥长度/类型错误、key-ref边界与消息歧义均拒绝且不回显密钥/签名/包正文。
- 定向与后端全量测试、wheel及GitHub hosted Windows Server 2025 runner验收；配套运行中 PG18/前端/包链回归继续由PR工作流完成。所有工作和临时内容只在runner D盘；不在用户本机运行。
- 不验证正式密钥仪式、Windows 11设备、Gate 3、Pilot或正式发行，不使用客户数据/外部AI。

## 执行状态

本CR在编码前登记；详细编码前检查见 `docs/progress/plg-01-a02-signature-verifier-precheck.md`。具体实现提交、验收结果、失败与后续差异按本文件追加更新。


### 编码前结构检查补充（2026-11-03）

现有 License 验签器位于 Owner 的 `application` 层，Plugin 模块已有相同分层约定；因此 PLG 验签器实现在 `modules/plugin/application/signature_verifier.py`，不在 domain 层新增重复公钥/密码学抽象。该路径调整不改算法、合同或Scope。


## PLG-01-A02 实施与验收记录（2026-11-03）

- 代码提交：`11a4e33448fc68718e43d8d7d3572ac2c703b6a8`；GitHub hosted run [41569062762](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41569062762) 全13 jobs成功。
- 纯验签器绑定完整归档SHA-256、Ed25519 detached signature和外部trusted signer Port；8项合成单测覆盖有效签名、篡改、撤销/禁用、无效key和key-ref边界。未添加DB/API/Migration。
- 结果：`PASS_SCOPE_LIMITED`。没有生产Trust adapter/公钥/撤销源，不能将包标记VERIFIED。完整证据见 `docs/progress/plg-01-a02-signature-verifier-result.md`。
- 下一项：PLG-01-A03 生产发布者公钥信任源与撤销边界编码前检查。
