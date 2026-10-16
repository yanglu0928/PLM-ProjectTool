# SOL-01-A04-P04-P05：PROJECT Reference List 签名游标与 HTTP/PG

日期：2026-10-09；结果：`REFERENCE_LIST_HTTP_PG_PASS`，限定为可注入路由和 Windows 11 隔离 PostgreSQL/ASGI；Windows 生产组合尚未挂载。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04、DEC-20261009-1115、P04-P04 List Owner
前置：Reference List Owner 的隔离PG与全量后端回归通过
涉及模块/实体：Solution List API 与独立游标 Codec；无 Schema/ORM 变化
涉及 API：可注入 PROJECT List；默认/Windows/GLOBAL 关闭
权限：当前 Session、有效 License、同项目 ACTIVE 成员、可信 Host
验收：游标签名/作用域/会话/页大小绑定、响应白名单、真实 ASGI/PG、负例和全量回归
风险：目标账户密钥供给/备份恢复、Windows 组合、List UI、正式信任源和性能待
```

游标仅接受 canonical 编码与正确 HMAC；原始 `after` ID 不进入 HTTP。摘要不返回正文或固定来源明细，不将 Reference 状态误称已批准。Windows 11 一次性隔离 PG18.6/私有文件的真实 SessionService/ASGI 验证两条 Reference 双页、Session/页大小游标重放拒绝、跨项目/暂停成员/License 拒绝；来源、PROJECT 创建和 drift 回归通过。合同单元 `3 passed, 13 subtests passed`，后端全量 `3318 passed, 3 skipped, 4896 subtests passed`。无 Schema、依赖或冻结 API Breaking Change；可撤路由插槽回滚，历史不变。测试签名钥仅存在隔离脚本，正式密钥待下项 Windows Vault 组合，不得据此认为用户端已开放。

TraceLink：API-04/DEC-1115 → List 增量合同 → ReferenceListCursorCodec/可注入 Router → 合同与真实 ASGI/PG 验证。
