# Developer Workbench

License 签发、Plugin 签名与 Release 制作的独立开发者信任区。它不进入客户运行包，不访问客户运行数据库或客户项目资料；私钥只允许存放在已忽略的 `tools/developer-workbench/private/` 本地目录，绝不提交 Git。发行私钥须以交互式强口令加密，并与口令分别离线备份；未验证独立恢复前不得发布。

在安装了项目固定 `cryptography` 依赖的 Python 3.13 交互终端运行 `python tools/developer-workbench/license_key_ceremony.py create`。工具隐藏输入两次至少 24 字节的口令，独占创建加密 PKCS#8 私钥和后端包内公钥清单；已有任一文件时拒绝覆盖。口令不能写在命令行、环境变量、聊天或 Git 中。

将加密 PEM 复制到工作台以外的受控离线介质，并将口令另行保管。把离线副本接回受控终端后，用 `python tools/developer-workbench/license_key_ceremony.py verify <绝对路径的离线私钥副本>` 验证其与包内公钥匹配；再对最终安装 wheel 运行 `python -m plm_assistant.entrypoints.verify_release_key`。本工具的合成单元测试不等于真实密钥、离线备份、ACL 和最终 wheel 验收。
