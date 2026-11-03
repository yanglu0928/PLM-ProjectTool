# Developer Workbench

License 签发、Plugin 签名与 Release 制作的独立开发者信任区。它不进入客户运行包，不访问客户运行数据库或客户项目资料；私钥只允许存放在已忽略的 `tools/developer-workbench/private/` 本地目录，绝不提交 Git。发行与插件签名私钥须以交互式强口令加密，并与口令分别离线备份；未验证独立恢复前不得发布。

License：
`python tools/developer-workbench/license_key_ceremony.py create`
创建加密PKCS#8私钥及后端包内公钥清单。

Plugin：
`python tools/developer-workbench/plugin_key_ceremony.py create`
使用独立Ed25519 key；工具初次运行只接受空的版本化 `plm.plugin.publisher-keys.v1` 清单，拒绝覆盖已有私钥/已登记发布者。公开清单位于Plugin模块的包内 `trust/developer_keys.json`，可随已审查的软件源码发行；私钥只在workbench ignored目录。使用
`python tools/developer-workbench/plugin_key_ceremony.py verify <绝对路径的离线私钥副本>`
校验离线副本与公开key-ref匹配。不得把私钥或口令写入命令行、环境变量、聊天、仓库或CI artifact。

真实仪式须由开发者在受控工作台交互运行；提供强口令并分别保管私钥密文和口令，离线副本接回后验证恢复。仅合成单测不等于真实密钥、ACL、备份或生产信任验收。撤销/轮换通过新key-ref及保留历史的REVOKED记录进行，不能覆盖旧签名历史。
