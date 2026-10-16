# CR-CAP-004：Capability 目标账户游标密钥仪式延期

日期：2026-10-05。状态：依据 `CR-EXEC-001` 持续授权采用可恢复替代控制；正式目标账户供给保持 Release 前置，未标记生产信任通过。

## 来源与冲突

`CAP-01-A05-A07` 原计划同时完成十二个冻结 Capability Operation 的 Windows 生产组合、真实 HTTP/PostgreSQL 验证和目标账户游标签名密钥供给。当前 Windows 账户不存在 `capability-baseline-cursor-v1` 与 `capability-child-cursor-v1`。仓库既有 Windows Vault 供给流程要求先生成加密恢复备份并由操作员持有独立口令；持续授权不允许 AI 自行代管口令或创建不可恢复的正式 Secret。

## 方案比较与选择

- 不选直接生成正式密钥但不做恢复备份：密钥丢失会使现有游标全部失效，且不符合既有 Vault 恢复控制。
- 不选把固定测试密钥写入配置、源码或 Git：会泄露签名材料并把合成信任冒充生产信任。
- 选择先完成失败关闭的生产组合代码，以隔离合成 Resolver 在临时 PostgreSQL 18.6 中验证十二个 Operation；正式目标账户密钥、加密备份、ACL 与恢复演练留作 Release 安全仪式。缺少任一密钥时生产组合拒绝启动。

## 差异、影响与回滚

差异仅是供给时序：冻结 API、数据模型、Schema0095、权限及游标合同不变。Windows `--platform` 组合挂载五个读取 Operation，`--platform-write` 挂载全部十二个；登录专用模式不挂载 Capability。两把密钥使用独立固定引用，不复用其他模块密钥。

回滚可停止向生产应用注入 Capability Router；已形成的 Capability/Review/Audit 历史不得删除。正式密钥尚未供给，因此没有 Secret 数据迁移。后续仪式必须生成两把独立随机密钥、加密恢复备份、记录保管人和 ACL，并在目标服务账户完成丢失/恢复与旧游标签名验证。

## 验证与剩余风险

Windows 11 以隔离合成密钥、临时 PostgreSQL 18.6 和真实 HTTP 完成十二个冻结 Operation、送审重放、限制、归档及迁移 drift 检查；缺任一密钥和非法组合模式均失败关闭。该证据只证明组合机制，不证明正式目标账户 Vault、备份恢复、Windows Server 2025、Debian 13、正式 License 信任或发行安装通过。
