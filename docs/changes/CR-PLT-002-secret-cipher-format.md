# CR-PLT-002：Secret 密文格式与算法定型

日期：2026-09-25；状态：IMPLEMENTED / PLT-02-A04 PASS（生产密钥来源未完成）。

来源：冻结 DM-02 要求数据库只保存密文/算法元数据与外部 key reference，主材料分离；原 Gate 2 基线未选定加密算法或 Windows/Linux `SecretKeyProvider`。PLT-02-A04 需一个可版本化、可验证的密文格式，不能以明文或可逆编码替代加密。

方案比较：A 使用已有 `cryptography` 的 AES-256-GCM，12 字节随机 nonce，16 字节认证 tag，AAD 绑定 SecretRef/用途/消费者/版本号/key ref；B 延后算法，先留抽象接口，但无法验证正式密文写入边界。选择 A；不新增第三方依赖。官方实现说明见 [cryptography AESGCM 文档](https://cryptography.io/en/latest/hazmat/primitives/aead/)（nonce 不得在同密钥下复用，错误 key/nonce/AAD/tag 均拒绝）。

差异：仅把原基线留白的算法定为 `AES-256-GCM-V1`，不改变密文与主材料分离、不决定主密钥驻留方式、不向客户侧提供 Ed25519 私钥。记录与 Schema/API 不变。

验证结果：合成一次性密钥往返、改密文/nonce/AAD/key 拒绝、随机 nonce 差异、输入清零、最大长度、旧格式拒绝；Windows 11/Python 3.13 后端 201/201、目标加密组件覆盖率 96%、PostgreSQL 18.6 临时库密文存储与错误密钥拒绝、wheel 构建 PASS。真实 OS 密钥保护、备份恢复、轮换以及断网三平台验收另由 PLT-02/Release 完成，不能在本项宣称生产 Secret Store 可用。

迁移与回滚：当前未有正式 Secret 写命令，既有临时库测试密文无生产意义；日后格式升级须增加算法版本并保留旧版读取或受控重加密，不得直接覆盖历史版本。代码回退不应删除密文历史。
