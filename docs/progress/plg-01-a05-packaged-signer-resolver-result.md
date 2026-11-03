# PLG-01-A05 结果：包内发布者公钥清单信任解析器

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- 提交：ce6a40e185cfa736208060d14030f0d17809131b
- 云端复验：[GitHub Actions run 41579068045](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41579068045)

## 变更

- 新增只读 packaged signer resolver，加载 backend wheel 中的版本化公开公钥资源并适配现有 TrustedPluginSignerResolver。
- 只返回精确 key-ref 且 ACTIVE 的 Ed25519 signer；未知、REVOKED、重复、未知字段、错误编码/长度、损坏或超限清单失败关闭。
- 产品仓库的 developer_keys.json 仍是空keys清单；不生成真实密钥，不联网、不接受包内自带key。
- 无数据库、Migration、API、ORM或默认插件安装/执行组合变化。

## 验证

- hosted run 41579068045 全13 jobs success；后端3,895项、frontend、wheel、PG18、非发行父包、A35/A17/A34成功。
- 6个Resolver专用测试通过；含内存合成Ed25519私钥的签名集成验证，未将合成key写入文件或artifact。
- 全部执行在GitHub hosted Windows Server 2025 runner；未在用户本机/C盘执行。

## 限制

PASS_SCOPE_LIMITED只证明包内清单读取与合成验签适配逻辑。当前正式资源没有Active key，因此真实Plugin包仍不可建立可信发布者身份；无动态撤销源、压缩包安全检查、导入/安装/执行、Win11实机、Gate 3、Pilot或Release证据。

## 下一项

PLG-01-A06：安全只读检查Plugin ZIP归档，解析根目录manifest.json、校验EntryPoint并联合验证完整归档detached signature。合同与边界见CR-PLG-004。
