# SOL-01-A04-P02-P03-P03-P03-P02：GLOBAL 确认真实来源组合

日期：2026-10-08；结果：`REAL_SOURCES_PG_PASS`，限定为内部合成资料/Document 级 Evidence，实际用户人工确认与运行入口未完成。

```text
当前 Phase：Phase 2
当前 WBS：SOL-01-A04-P02-P03-P03-P03-P02
输入基线：冻结 DM-05/API-04、CR-SOL-006、0142 与既有 Auth/Document/Evidence 受权 Proof
前置：内部确认/读取/撤销、真实 Auth Session/CSRF 组合已通过
涉及模块/实体：Solution 资格/确认；Auth Session；DocumentVersion/FileObject；Evidence
API/权限：无公开 API；当前 DeploymentAdmin，License 为合成许可 Port
验收：PG/私有文件来源一致、资格可读；错误范围、物理篡改、Evidence/确认撤销失败关闭
风险：用户/文件/License 均为测试材料；未覆盖解析节点 Evidence、登录/HTTP/人工操作
```

Windows 11 一次性 PG18.6/pgvector 与独立私有目录中创建合成 GLOBAL `REFERENCE_MATERIAL` 文件、DocumentVersion、Document 级 `ELIGIBLE` Evidence 以及管理员 Session。使用真实 Auth、Document 身份/固定来源证明、Evidence 当前记录/固定来源证明、Solution 资格/确认/撤销仓储；仅 License 有效性以合成 Port 代替。确认前复核物理文件 SHA-256，确认后 `qualify` 返回对应确认 ID；错误 PROJECT 范围拒绝。改变私有文件字节后资格拒绝；恢复文件后撤销 Evidence，来源证明拒绝；确认独立撤销后当前确认 Proof 拒绝。脚本退出0，Alembic drift 为无新增操作，临时实例与目录清理。

验证中尝试复原已 `REVOKED` Evidence 被数据库规则拒绝；尊重不可逆历史，不改生产约束。故以来源 Proof 验证 Evidence 撤销，以独立确认 Proof 验证确认撤销。不能由脚本合成的管理员及声明推定实际人工脱敏已核查；正式登录、真实许可、解析节点 Evidence、公开 HTTP/UI 和 ReferenceVersion 绑定均待后续任务。TraceLink：CR-SOL-006 → DEC-20261008-1109 → 内部 PG/物理文件脚本 → 后续 Reference Owner/人工入口。
