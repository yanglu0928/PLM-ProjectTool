# PLG-01-A02 结果：Ed25519 插件包签名验证器

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- 分支：feature/p51-a33-launcher-checksum-recovery
- 代码提交：11a4e33448fc68718e43d8d7d3572ac2c703b6a8
- 设计变更：[CR-PLG-001](../changes/CR-PLG-001-plugin-package-signature-format.md)
- GitHub hosted 验收：[run 41569062762](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41569062762)，13/13 jobs success

## 实现内容

- 在 `modules/plugin/application` 新增 `PluginPackageSignatureVerifier`、`TrustedPluginSignerResolver` Port及独立的Plugin信任/验签结果类型。
- 只接受完整归档 bytes、64-byte Ed25519 detached signature与外部 Resolver 返回的32-byte raw公钥。
- SHA-256覆盖传入的全部归档字节；Ed25519消息按CR-PLG-001固定为域分隔、2-byte key-ref长度、key-ref UTF-8及32-byte摘要。包内公钥不参与信任解析。
- 未知、非活动、撤销、格式错误或解析器异常均失败关闭；异常只返回稳定错误码，不回显包正文、签名或公钥。
- 不调用数据库/HTTP/网络，不更新A01 Package状态，不解析Manifest或运行插件；没有Schema/API/Migration变化。

## 验收结果

- 8项新增合成单测：成功签名、完整包篡改、签名篡改、未知签发者、禁用/撤销状态、损坏公钥、Trust Resolver异常、输入/key-ref边界和域消息防歧义，均通过。
- GitHub hosted run 41569062762 的后端全量测试与wheel、前端测试/typecheck/build、PG18/pgvector临时数据库、父包组装、A35交接、A17 PlanVersion Edge/HTTPS/PG及A34替换/恢复均成功。
- Secret检查通过；密钥在单测进程内随机生成，不保存到仓库或构建产物。所有执行和临时工作目录位于GitHub hosted runner的D盘空间；用户本机未运行代码。

## 证据边界

仅验证算法实现与注入式合成Trust Port。当前没有生产发布者公钥、签发/撤销管理或可信工作台装配；没有真实包被验证或置为 `VERIFIED`。本验签结果不证明Manifest、兼容性、依赖、路径或恶意代码安全。未做Windows11实机、Gate 3、Pilot或正式Release验收。

## 下一项

PLG-01-A03：生产发布者公钥信任源与撤销边界编码前检查。必须先确定外部keyring来源与安全更新/撤销规则，再接入实际包状态转换。


## 后续顺序调整（2026-11-03）

正式 signer trust source 尚无可核实开发者发布根密钥或撤销材料，不能安全装入真实公钥。按 DEC-PLG-001，先实现不依赖信任根的只读 Manifest 解析/入口路径校验（PLG-01-A03，CR-PLG-002），再单独处理信任源和密钥仪式。A02通过合成key的验签结果继续为 `PASS_SCOPE_LIMITED`，不代表生产包可验证。
