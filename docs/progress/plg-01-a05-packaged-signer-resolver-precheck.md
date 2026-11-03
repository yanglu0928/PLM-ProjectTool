# PLG-01-A05：包内发布者公钥清单信任解析器编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A05
- 上一项：PLG-01-A04 PASS_SCOPE_LIMITED
- 输入CR/基线：CR-PLG-001（签名算法与消息格式）、CR-PLG-002（Plugin manifest）、CR-PLG-003（publisher key清单格式/工作台仪式）、冻结ADR-005/API-03/DM-04
- 执行约束：只在GitHub hosted CI测试合成公钥；不在用户本机运行；tracked清单保持空，无真实信任材料。

## 单一目标

实现包内 plm.plugin.publisher-keys.v1 清单的只读受信任签名者解析器，适配现有 TrustedPluginSignerResolver。只允许清单中精确key-ref、Ed25519 raw public key与ACTIVE状态返回signer；未知、REVOKED、损坏、重复字段或超限清单一律失败关闭。不安装、不导入、不启动任何插件。

## 编码前检查

|检查|证据与结论|
|---|---|
|现有Verifier契约|A02的 TrustedPluginSignerResolver Protocol 要求 resolve_trusted_signer(key_ref) 返回 TrustedPluginSigner 或 None；Verifier已检查key-ref一致、ACTIVE、32-byte key，并把异常统一映射为 PLUGIN_SIGNER_UNTRUSTED。本WBS只实现资源解析适配器，不改Verifier合同。|
|输入信任格式|CR-PLG-003固定根字段 schema_version/keys，key记录 key_ref/algorithm/public_key/state；清单当前严格为空。运行时信任来自软件包受控资源，不接受包内自带key、用户参数、公网发现或网络下载。|
|前置完成|A04结果文档与CR状态为PASS_SCOPE_LIMITED；tracked manifest schema现存，backend pyproject已声明package-data。生产key/轮换仪式尚未完成，故正向验签只能使用内存合成私钥并明确属于测试。|
|范围|新增 modules/plugin/infrastructure/packaged_signer_resolver.py 和单测。应用层Verifier、ManifestParser、Package ORM/API、数据库、License、路由与工作台真实仪式均不修改。|
|实体/API/权限|无新增持久实体、migration、API、用户操作或权限；只读软件包内公钥资源。|
|边界|未知/REVOKED key返回None或抛出非敏感配置错误，Verifier统一失败为 PLUGIN_SIGNER_UNTRUSTED；真实包内空manifest因此拒绝所有签名。严格限manifest字节与key数量，拒绝duplicate JSON keys、unknown fields、bad base64、长度/编码/算法/状态错误。|
|验收|云端定向测试合法Active解析、unknown/ref错配、REVOKED拒绝、空keyring失败关闭、畸形/重复/未知/超限清单拒绝、合成签名验证集成、source resource加载与wheel包含空清单；后端全量和PR Cloud Sandbox集成链通过。|
|回滚|只移除新增Resolver与测试，不触及schema/API/数据库；默认空manifest保持信任关闭。|
|Secret检查|只用云端进程内合成Ed25519私钥；私钥不落仓库、不上传artifact、不写日志；推送前扫描变更并核对远端head。|

## 预计修改文件

- 新增 apps/backend/src/plm_assistant/modules/plugin/infrastructure/packaged_signer_resolver.py
- 新增 apps/backend/tests/unit/test_packaged_plugin_signer_resolver.py
- 必要时只补充该类的trust resource package-data测试，实际格式沿用CR-PLG-003，不改空清单内容。
