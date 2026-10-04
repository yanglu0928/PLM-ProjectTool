# PLT-02-A01：SecretRecord / SecretVersion ORM 与迁移

- 日期：2026-09-24；结果：PASS（仅数据层）；依据：Gate 2 冻结 DM-02/SC-01～03、API-02、CR-EXEC-001、DEC-20260924-097。
- Changed：新增部署级 SecretRecord 身份及密文 SecretVersion 历史。字段只含用途、受控消费者、密文字节、算法元数据与外部 Key Provider 引用；无明文/主密钥字段。复合 FK 防止 current_version_ref 跨记录，partial unique 限定同记录最多一个活动版本；触发器限制密文历史不可修改/删除，仅允许版本激活和退役，记录状态需 lock_version 递增。非空 Secret 历史拒绝普通降级。
- Files：`secret_orm.py`、Alembic `20260924_0011_secret_record.py`、迁移注册/契约测试、`validation/plt-02-a01-secret-schema/verify.py`、决策/版本/状态文档。Migration：`20260924_0011`，升级前备份，执行 `upgrade head`；有 Secret 历史不能普通降级。API：无公开路由。Permission：本项仅存储，正式写命令和 DeploymentAdmin/License/CSRF/Audit 待后续 WBS。
- Tests：Windows 11/Python 3.13 后端 188/188 PASS；PostgreSQL 18.6 临时库空库 up/down/re-up、已有 User 数据升级、ORM drift=0、用途/消费者与活动唯一/跨父引用/密文不可变/历史保护、非空回退拒绝 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：此层不加密、不解密、不装配跨平台 SecretKeyProvider，不能认为生产 Secret Store 可用；PLT-02 write-only 命令、读适配、权限/审计与恢复验证未完成。测试密文字节为合成无意义值，不是客户 Secret。
- Next：`PLT-02-A02 Secret 元数据读取与受控加密信封适配`，先实现只读且不泄漏密文的查询边界；生产密钥来源仍由 Release 安全设计处理。
