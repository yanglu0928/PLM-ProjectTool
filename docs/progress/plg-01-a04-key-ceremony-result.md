# PLG-01-A04 结果：Developer Workbench 插件签名密钥仪式

- 日期：2026-11-03
- 状态：PASS_SCOPE_LIMITED
- 编码提交：19b214ae777b2b899509639ae3c31b934ef31479
- 回滚修复：aaef9391b0a98b8b202e5140f7266b8a0a8841a0
- 云端复验：[GitHub Actions run 41576991044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41576991044)

## 变更

- 增加 Developer Workbench 插件 Ed25519 签发密钥创建/核验工具，Encrypted PKCS#8 私钥固定在 ignored workbench private 路径；真实 key ceremony 本轮未执行。
- 增加版本化 plm.plugin.publisher-keys.v1 公钥清单空模板并将其声明为 backend wheel package data。
- 增加合成key云端测试：创建/匹配核验、离线副本、口令错误、清单/路径拒绝、不覆盖保护、发布后核验失败回滚。
- 编码后审查发现首次发布回滚缺口，先登记于CR后修复：pair核验失败恢复原空清单；只有恢复成功才清理新私钥，恢复失败时保留与当前ACTIVE记录配对的加密私钥，避免孤立信任条目。
- 无 ORM、Migration、API 或客户运行组合变化。

## 验证

- 首轮hosted run [41575141107](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41575141107)：13/13 jobs成功。
- 修复后hosted run [41576991044](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41576991044)：13/13 jobs成功。后端3,889项、仪式工具5项、wheel、前端、PG18、父包、A35/A17/A34通过。
- Hosted Windows Server 2025 runner；所有本WBS的合成私钥测试限定于runner临时目录；没有在用户本机/C盘运行程序。
- Secret pattern扫描无命中。

## 限制

本项只证明合成输入下的工作台工具逻辑，不证明真实密钥创建、访问控制、离线介质保管/恢复、runtime trust active key、Windows 11实机、Gate 3、Pilot或Release。公开清单保持空集合，运行时必须拒绝全部真实Plugin签名。

## 下一项

PLG-01-A05：读取包内发布者公钥清单并实现 fail-closed TrustedPluginSignerResolver。
