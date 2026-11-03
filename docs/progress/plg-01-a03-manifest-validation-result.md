# PLG-01-A03 结果：版本化 Plugin Manifest 解析与入口路径校验

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- 分支：feature/p51-a33-launcher-checksum-recovery
- 最终源码提交：9abfa92316f0a91e1e20360a858d794173e4f7bf
- 格式变更：[CR-PLG-002](../changes/CR-PLG-002-plugin-manifest-v1.md)
- GitHub hosted 验收：[run 41573036147](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41573036147)，13/13 jobs success

## 实现

- 增加只读 `plm.plugin.manifest.v1` parser，严格允许版本化根/operation/dependency字段；重复JSON键、未知字段、无效类型或schema版本失败关闭。
- Manifest UTF-8上限65,536 bytes、结构深度16、节点4,096、operations 128、dependencies 256；仅支持冻结目标Windows 11/Windows Server 2025/Debian 13 x86_64。
- 校验插件ID/语义版本、operation唯一性和output_types、dependency种类/唯一性；dependency只是声明，不解析/下载/安装。
- 入口只接受规范相对POSIX路径，拒绝绝对路径、drive/UNC、反斜杠、NUL、冒号、空段、`.`/`..`及规范化歧义。
- 返回冻结dataclass投影与稳定canonical JSON SHA-256；无文件系统、ZIP、数据库、网络、API、Migration、导入或执行操作。

## 验收

- 修正测试fixture后，Manifest和入口用例实际传入UTF-8 JSON bytes；有效、未知/缺失/重复字段、schema/OS/API、无效JSON/非UTF8/非有限数、大小/深度/节点、operation/dependency、路径攻击等用例通过。
- GitHub hosted Windows Server 2025 run 41573036147 共13/13 jobs成功：后端3,889全通过和wheel、前端typecheck/build、PG18/pgvector、候选父包、A35 handoff、A17 PlanVersion Edge/HTTPS/PG、A34隔离替换/显式恢复均成功。
- Secret scan通过；仅合成数据；所有临时工作在runner D盘，本机未运行代码。

## 失败和测试盲区更正

run 41571211968、41571779122、41572410413 曾在入口路径错误码断言失败。最初依据不完整日志将首轮误判为“NUL错误分类”；随后发现实际根因是测试 `reject()` 将dict直接传给bytes-only parser，结构用例提前停在输入类型守卫。此前两次Parser错误分类调整没有被这些测试有效覆盖。该判断已在后续追加记录中纠正。run 41573036147 修正helper为dict先编码UTF-8 JSON并增加路径subTest后，全量通过。上述失败都没有证据表明真实路径校验有绕过；在最终run之前也未宣称该功能通过。

## 证据边界

结果只证明版本化Manifest纯解析和入口字符串安全边界。没有验证实际ZIP条目/符号链接/解压炸弹、签名者生产信任源、包导入/持久状态、运行兼容、安装/执行或恶意代码安全。正式Trust adapter、密钥轮换/撤销与工作台根密钥仍待。结果不是Windows 11实机测试，也不关闭Gate 3/Pilot/正式Release。

## 下一项

PLG-01-A04：生产发布者公钥信任源、密钥轮换与撤销边界编码前检查。
