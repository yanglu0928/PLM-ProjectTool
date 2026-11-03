# PLG-01-A04：Developer Workbench 插件签名密钥仪式编码前检查

- 日期：2026-11-03
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A04
- Change Request：CR-PLG-003（先记录密钥格式/工作台路径）
- 上一项：PLG-01-A03 PASS_SCOPE_LIMITED；真实Plugin signer trust root未生成
- 执行：只在GitHub hosted Windows Server 2025 runner测试合成key；本轮不创建真实key，不在用户本机运行

## 单一目标

新增 Developer Workbench 插件签发Ed25519 key ceremony和版本化公开key manifest生成/恢复验证，使未来能由受控开发者产生插件签名key；本项不实现客户运行时trust adapter，不执行真实仪式。

## 编码前检查

|检查|证据与结论|
|---|---|
|Developer Workbench规则|读取tools/developer-workbench/README.md与现有license_key_ceremony.py：私钥仅在被忽略private目录；PKCS#8加密，隐藏交互口令，首次文件独占创建，离线副本单独验证；本WBS遵循同型约束。|
|签名基线|CR-PLG-001规定Ed25519，消息域绑定完整Package SHA256与key-ref；A02 verifier收外部Trust Port，不接受包内公钥。License与Plugin必须分离key。|
|信任材料|新增versioned public manifest `plm.plugin.publisher-keys.v1`，只包含key refs/algorithm/public key/state；运行时是否读取留给后续任务。本项不生成真实key。|
|Owner/隔离|工具仅在 `tools/developer-workbench`，排除客户runtime package。公钥仅放置backend plugin trust resource并在wheel中声明；私钥仅Git-ignore路径。|
|验收边界|first-create拒绝覆盖任何已存在私钥/清单；private/public一致验证；输入/错误均不回显；模拟离线备份恢复；symlink及不安全路径失败。真实磁盘ACL/独立备份由未来仪式完成，不虚报。|
|依赖/数据|使用backend已pin cryptography 50.0.1；无客户包、账户、网络、API、DB schema或Migration。测试key只在runner临时目录，任务结束清理。|
|失败/回滚|工作台工具在客户包外；若云端失败则不生成发布Key清单，保持Trust空集合/包导入关闭。无数据库迁移和真实key搬迁。|
|Secret检查|代码库仅含ceremony实现及空公钥清单；不提交私钥、口令、测试密钥或日志。提交前Secret scan并hosted验证。|

## 编码范围

预计新增 `tools/developer-workbench/plugin_key_ceremony.py`、`apps/backend/src/plm_assistant/modules/plugin/trust/developer_keys.json`、工具单测和pyproject package-data一行；只含空清单schema，不含真实公钥。更新CR/STATUS/CHANGELOG/结果。


## 首轮hosted实现后审查补充（修复前记录）

- 首轮run [41575141107](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41575141107)全13 jobs成功，包括本WBS合成仪式单测、后端全量/wheel。
- 复核发现异常回滚不完整：新公钥清单替换成功、后续pair核验失败时，工具会删私钥但未恢复已替换清单，可能留下ACTIVE孤立公钥。
- 修复计划按CR-PLG-003：先留存旧空清单原始字节；任何失败均清理新私钥/暂存文件并原子恢复旧清单；新增发布后核验失败注入测试。提交该修复前，本问题已先记录于CR、STATUS与CHANGELOG。A04不得在修复与云端复验前标记完成。
- 不涉及客户数据或真实key；所有测试继续只在GitHub hosted D盘runner temp生成合成key。


## 最终验收

- 首轮hosted run [41575141107](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41575141107)全13 jobs成功后代码审查发现回滚缺口；缺陷先记录于CR-PLG-003、STATUS/CHANGELOG，再提交修复aaef9391。
- 修复后hosted run [41576991044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41576991044)全13 jobs成功。后端3,889项/合成仪式5项、wheel、前端、PG18、父包及A35/A17/A34通过。
- 回滚注入用例确认核验失败时恢复原空清单、删除新密钥且没有遗留临时文件；Secret扫描无命中。
- A04结论：PASS_SCOPE_LIMITED。没有生成真实密钥或验证真实ACL/离线介质/生产Trust。本机未运行。
