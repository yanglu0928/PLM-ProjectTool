# PLT-02-A07-P03-A03：Developer Workbench 签发密钥仪式

- 日期：2026-09-25；状态：工具与合成测试 PASS / 真实密钥仪式和独立备份 NOT DONE；本项未 PASS。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P03-A03。输入：ADR-006、CR-LIC-001、P03-A02 包内公钥解析和发行门禁。工具开发前置满足，真实签发需工作台操作员保管强口令。
- 发现：原 `.gitignore` 中 `developer-workbench/private/` 只覆盖仓库根级路径，实际 `tools/developer-workbench/private/` 的非 `.pem` 文件未被整体忽略。已添加实际目录绝对仓库路径规则，使用 `git check-ignore -v` 验证 `.pem` 和 `.p8` 均匹配新规则。
- 实现：独立于客户 wheel 的 `license_key_ceremony.py` 只允许交互终端，从隐藏输入接收强口令；独占创建口令加密 PKCS#8 Ed25519 私钥及固定本产品公钥清单；拒绝覆盖已有签发身份；支持从绝对路径的离线私钥副本验签核对。私钥不输出至标准输出、日志、Git 或客户包。
- 验证：Windows 11/Python 3.13 后端 343/343 PASS；临时目录合成密钥覆盖加密 PEM、错误/短口令、重复创建拒绝、公私钥匹配及独立文件副本验证，临时文件由测试清理。真实工作台 private 目录与真实公钥清单仍不存在；没有生成正式私钥。开发 wheel 构建 PASS，不等于 Release PASS。
- 待完成：由能保管强口令的工作台操作员运行真实仪式，分别离线备份加密私钥与口令，从独立副本核验；复核文件 ACL、最终 wheel 仅包含公钥且发行门禁通过，完成真实签发→验签。未完成前 P03-A02/P03-A03 和生产 License 装配均不得标 PASS。Windows Server 2025 未验证；Debian 13 按用户要求暂不验证。
