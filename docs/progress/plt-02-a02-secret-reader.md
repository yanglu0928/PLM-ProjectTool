# PLT-02-A02：活动密文信封只读适配

- 日期：2026-09-25；结果：PASS（仅内部只读适配）；依据：Gate 2 冻结 DM-02/API-02、CR-EXEC-001、DEC-20260924-098。
- Changed：SQLAlchemy 适配器按 SecretRef 读取 ACTIVE 记录所指向的同父、已激活且未退役版本，返回既有 SecretEnvelope；未激活、停用或缺失直接拒绝。元数据以确定性 UTF-8 JSON 字节传递给既有 SecretResolver，后者仍在授权消费者单次使用范围内解密、审计并尽力清零。适配器不提供通用密文列表、管理 API 或解密实现。
- Files：`secret_store_reader.py`、单元测试、PostgreSQL 临时库验证脚本、状态/决策/版本文档。Migration：无。API：无公开路由。Permission：消费方由既有 SecretResolver 的 Purpose × Consumer 白名单检查；管理元数据权限不在本项。
- Tests：Windows 11/Python 3.13 后端 191/191 PASS；适配器单元+PostgreSQL 集成覆盖率 91%；临时库未激活/停用拒绝、活动版本读取、错误消费者拒绝、单次缓冲区清零 PASS；wheel 构建 PASS。Windows Server 2025、Debian 13 本任务未运行。
- Known Issues：集成脚本使用合成密文与合成解密器，不证明生产加密或 SecretKeyProvider。数据库中尚无正式受控写命令、管理员元数据 API 或生产 Key Provider；不可接入真实 API Key。
- Next：`PLT-02-A03 Secret 管理元数据只读查询与权限边界`；写入/轮换及生产主密钥另行按依赖推进。
