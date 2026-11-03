# CR-PLG-003：Developer Workbench 插件签发密钥与发布者清单

- 日期：2026-11-03
- 状态：APPROVED_BY_CONTINUOUS_USER_AUTHORIZATION / IMPLEMENTATION_IN_PROGRESS
- 适用 WBS：PLG-01-A04
- 依据：ADR-005、Module Boundaries、DM-04、CR-PLG-001/002、Developer Workbench既有License key ceremony规则、用户持续自主执行授权

## 问题

PLG-01-A02/03已有Ed25519 verifier与Manifest parser，但没有Developer Workbench插件签发私钥、公开发布者Key清单或可恢复仪式。没有真实key就不能建立生产信任，不能用License key或合成测试key冒充。

## 受限决定

1. 新增工作台专用插件 Ed25519 key ceremony；私钥仅写入被Git忽略的 `tools/developer-workbench/private/plugin-signing-v1.pem`，使用交互式强口令加密PKCS#8。命令、环境变量、普通日志不承载口令/私钥。
2. 公开信任材料使用版本化 `plm.plugin.publisher-keys.v1` JSON，收录 `key_ref`、`algorithm=Ed25519`、base64 raw 32-byte public key和 `state=ACTIVE|REVOKED`。客户运行包只包含公开材料；没有私钥或口令。
3. 初次创建时任何既有私钥或公钥清单都拒绝覆盖；验证既有加密私钥与当前公共材料匹配；验证离线副本须显式传入绝对路径。
4. 真实仪式必须由开发者在受控工作台执行，独立保管口令和加密私钥离线副本，并验证恢复。代码/合成测试不代表真实仪式完成。
5. 轮换/撤销通过保留旧key_ref并将状态设为REVOKED，再新增新key_ref；该追加/发布操作将在运行时清单消费WBS中独立实现，任何已有包的历史signature不被覆盖。

## 影响与兼容性

- 仅新增开发者工具、公钥清单格式/空模板及package-data声明；不新增客户API、数据库Schema、ORM、Migration或运行时信任组合。
- 使用已锁定 `cryptography==50.0.1`，无新依赖。
- 私钥绝不提交仓库或传到Actions artifact；云端测试只在runner临时目录生成并销毁synthetic key。真实私钥不在本轮生成。
- 现有License签名key与Plugin publisher key完全分离；不能跨用途或共享key ref。

## 风险

- 加密私钥仍要求强口令和独立离线备份；测试无法验证用户实际磁盘ACL、离线介质保管或恢复仪式。
- 公钥清单只有在运行时信任适配器将它作为只读、包内受控材料时才有效；本WBS不声称运行时已经读取或有可信发布者。
- 此信任证明开发者key对包的签名，不保证插件代码安全，ADR-005无强沙箱。

## 回滚与验证

- 工作台工具不进入客户wheel；无数据库回滚。若测试失败，删除未发布工具/空清单并保持Plugin导入关闭；真实key不存在，无key搬迁。
- 合成云端测试覆盖首次创建、既有文件不覆盖、口令长度/TTY拒绝、错误key型别、pair mismatch、离线副本验证、路径symlink/非绝对路径拒绝、公钥清单schema、输出不泄露secret及含客户包拒绝。
- GitHub hosted Windows Server 2025 runner D盘temp执行单测、后端全量/wheel和PR集成链；不运行用户本机，不执行真实key仪式或导出密钥。

详细编码前检查见 `docs/progress/plg-01-a04-key-ceremony-precheck.md`。本CR在编码前提交。
