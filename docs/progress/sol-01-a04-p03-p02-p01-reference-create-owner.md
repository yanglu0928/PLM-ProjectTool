# SOL-01-A04-P03-P02-P01：Reference 首版受控 Owner

日期：2026-10-08；结果：`GLOBAL_REFERENCE_CREATE_OWNER_INTERNAL_PG_PASS`；PROJECT 真实文件/PG 组合未验，P03-P02 整体继续。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P03-P02-P01
输入基线：冻结 DM-05/API-04、CR-SOL-004/005/006/007，Schema0139/0143
前置：真实 GLOBAL Auth/Document/Evidence PG/私有文件 Proof 与0143静态绑定通过
涉及模块/实体：Solution Reference 根、首版、固定 Document/Evidence 引用；Project 授权策略
API/权限：内部命令，无公开 API；GLOBAL 当前 DeploymentAdmin，PROJECT PM/IM（后者仅单元验证）
验收：原子写、首次结果重放、Audit失败回滚、历史只增/降级保护、当前来源/确认重验
风险：PROJECT真实PG未验；正式License/用户人工核查/HTTP/UI/Eligibility/Review未装配
```

0144 将 Reference 四表的触发器限定为仅 INSERT；本任务不打开更新、删除或截断。内部新建命令两次检查当前 Session/CSRF，独立 License Guard，写事务中再次通过来源资格合同核 Document/Evidence 当前文件与 GLOBAL 确认。服务端由名称、范围、来源集合指纹、有序来源 ID、类别和适用性计算版本 `content_fingerprint`，与 0143 独立的 `source_fingerprint` 分开。一次事务插入根（指向预分配的首版 ID）、版本、有序来源、Audit 和持久幂等收据；首回执固定 `REFERENCE_ONLY`、`DRAFT`、`"v0"`，不把参考材料自动批准为正式方案。

Windows11 隔离 PG18.6/私有源文件和解析结果真实 GLOBAL 组合：正确创建与同 Key 重放、错误 CSRF/同 Key 异载荷拒绝、Audit 失败回滚、四表历史拒改/拒截断、空表0144降级重升、非空拒降和 Alembic drift 通过。PROJECT 角色策略（PM/IM 允许，客户角色或归档项目拒绝）以单元验证；后端全量3301通过、3跳过、4831子例。未运行 PROJECT 真文件/PG 组合、正式发行 License、真实登录/人工脱敏确认、公开 API/UI、后续版本/Eligibility/Review/Trace/Workflow。TraceLink：CR-SOL-004/007 → DEC-20261008-1111 → 0144/内部 Owner → 隔离 PG/单元 → PROJECT 真实组合。
