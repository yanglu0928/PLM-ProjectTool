# PLT-02-A07-P01：Windows Secret 主密钥读取来源

- 日期：2026-09-25；状态：Windows 11 本机适配器 PASS，生产供给与恢复 NOT VERIFIED。
- Phase/WBS：Phase 2 Platform Core / PLT-02-A07-P01。输入：Gate 2 冻结密文/主材料分离合同、PLT-02-A05 AES-256-GCM-V1、CR-PLT-003。前置均满足本项只读适配器开发。
- 涉及 Platform 基础设施与测试；不改实体、Schema/Migration、公开 API 或权限。验收：严格 key_ref、当前 Windows 账户 Generic Credential 只读取精确 32 字节、缺失/异常失败关闭、可被现有加解密服务注入。
- 实现：`WindowsSecretKeyProvider` 将受限 key_ref 映射到 `PLMProjectTool/SecretKey/<ref>`；不生成、写入、轮换、导出、记录或自动恢复密钥。Windows Credential Manager 凭据属于当前登录账户的 credential set，不等于跨机恢复能力。Microsoft [CredReadW](https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credreadw) 与 [安全凭据处理](https://learn.microsoft.com/en-us/windows/win32/secbp/handling-passwords) 为平台选型依据。
- 验证：Windows 11/Python 3.13 后端 331/331 PASS；测试使用 UUID 命名的合成 Vault 条目，验证缺失、非法引用、非法长度、AES-GCM 加解密，结束删除该测试条目。未写入真实主密钥。无数据库或外部数据操作。
- 风险/下一项：当前读取接口并不构成生产 Key Provider 完成；先设计受控供给、独立加密备份与异机/异账户恢复、失密失败关闭，再装配 Secret API。Windows Server 2025 未验证；Debian 13 保持目标但按用户要求暂不验证。公开 Secret 路由保持 404，Gate 3/Release 未通过。
