# SOL-01-A04-P02-P03-P02：GLOBAL 人工脱敏确认内部命令

日期：2026-10-08；结果：`CONFIRM_OWNER_INTERNAL_PG_PASS`，不是运行 HTTP/真实人工确认 PASS。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P02-P03-P02
输入基线：冻结 DM-05/API-04、CR-SOL-005/006、Schema0140
前置：Document/Evidence 受权来源 Proof 与闭锁确认记录
涉及模块/实体：Solution 来源证明、人工确认应用命令/Repository、Audit/收据、触发器0141
API/权限：未增加公开 API；命令要求当前 Session+CSRF 的 DeploymentAdmin、有效 License 和固定人工声明
验收：同事务来源重验/指纹绑定、有效期、拒绝/重放、Audit 回滚、PG 升降与全量回归
风险：PG夹具来源/管理员为合成 Port；实际确认页面、真实登录/文件闭环、Proof读取与撤回未完成
```

`prove_sources` 将 Document/Evidence 当前固定证明和 GLOBAL 确认分层，不允许未确认来源直接调用 `qualify` 形成正式资格。确认命令重验现时来源，不接受客户端提供的来源 SHA；它要求字面人工声明、当前管理员 Session/CSRF、License，最长 30 天失效，并在同一事务内完成记录、Audit 与持久幂等收据。重放只返回原确认且不得在失效后复活；Audit 出错不提交。没有 UI/HTTP 挂载、也没有使用客户数据或生成任何真实确认。

验证：定向 13 passed/5 subtests；Win11 隔离 PG18.6 0141 升降/历史/漂移及合成命令单写、重放、Audit 回滚 PASS；后端全量 `3290 passed, 3 skipped, 4820 subtests passed`。TraceLink：CR-SOL-006 → 0140/0141 → 本命令/测试 → DEC-20261008-1105 → P03-P03 受权 Proof/撤回。
