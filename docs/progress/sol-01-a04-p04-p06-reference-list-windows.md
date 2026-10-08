# SOL-01-A04-P04-P06：Windows Reference List 独立游标密钥与显式组合

日期：2026-10-09；结果：`REFERENCE_LIST_WINDOWS_PG_PASS`，限定 Windows 11 当前账户临时密钥/隔离 PG 合成验证；正式目标服务账户未供给。

```text
当前 Phase：Phase 2 Platform Core
输入基线：Gate 2 API-04、DEC-1115、P04-P05 List签名游标HTTP
前置：List Owner、HTTP合同及隔离ASGI/PG通过
涉及模块：Windows当前账户SecretKeyProvider、Solution List组合与production_login装配
涉及实体/Schema：无数据库变化
涉及 API：显式--platform/--platform-write PROJECT List；默认/GLOBAL关闭
权限：真实Session/License/项目成员；缺KeyRef或依赖则启动拒绝
验收：独立KeyRef、临时Vault丢失/备份恢复、模式404/200/403、PG、全量回归
风险：正式服务账户密钥/离线备份、Server2025、性能/UAT/发行仍待
```

List 使用独立 `project-reference-list-cursor-v1` KeyRef，从当前 Windows 登录账户 Credential Manager 只读解析。无密钥、错长度或构造失败时显式平台应用启动拒绝；不复用 Document/ProjectMember 游标密钥，不在配置或日志内写入密钥。此轮仅在随机临时 KeyRef 上验证新钥供给、Vault 丢失和离线备份恢复后旧游标可验证；未向正式 KeyRef 写入任何密钥。目标运行账户需在交互式终端使用既有 `python -m plm_assistant.entrypoints.secret_key_recovery provision project-reference-list-cursor-v1 <绝对离线备份路径>`，隐藏输入恢复口令并将备份/口令分开保存；实际供给及异账户恢复留发行验收。

只读模式 List GET 打开时保留同路径 POST 的既有 404，写模式独立创建路由优先；该兼容决定见 `DEC-20261009-1116`。默认模式与 GLOBAL 仍关闭。Windows 11 一次性隔离 PG18.6/私有文件、真实 SessionService/ASGI 验证双页、跨项目拒绝、只读 POST 404、默认 GET 404、License 403，来源/创建/drift回归通过。生产模式合同和缺钥拒启动、临时 Vault 恢复单元通过；后端全量 `3322 passed, 3 skipped, 4904 subtests passed`。无 Schema、冻结 API 或新依赖；移除 List 显式装配可回滚，历史不变。正式 License、目标账户、Windows Server 2025、Debian 13、20 并发、UI、Gate3/发行不因本项通过。

TraceLink：API-04/DEC-1115 → P05 List HTTP → DEC-1116 → Windows独立KeyRef/组合 → 临时Vault/模式合同/隔离PG/全量回归。
