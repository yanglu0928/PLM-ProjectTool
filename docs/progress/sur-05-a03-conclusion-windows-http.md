# SUR-05-A03：SurveyConclusion Windows 组合与真实 HTTP/PG 闭环

日期：2026-10-07。结论：`SUR_05_A03_CONCLUSION_WINDOWS_HTTP_PASS`。下一项：`SUR-05-A04`
严格前端客户端与 Conclusion 工作台。

## 基线与目标

- Phase 2 / SUR-05；输入为冻结 API-04、CR-SUR-009、A04～A06 Owner 与 A02 五 Operation HTTP。
- 仅把既有 LIST、CREATE、GET、VALIDATE、SUBMIT_REVIEW 接入 Windows 显式生产组合，并让通用
  PROJECT Review Router 注册 `SRV-05`；不增加公开路径、Schema、依赖、License 权益或外发。
- 默认应用继续 404；只读平台只开放 LIST/GET；缺少 Document/Download/Parse 三项完整证明依赖时，
  Conclusion 写与 `SRV-05` Review Owner 均失败关闭。

## 实施

- Conclusion cursor 由既有 Survey cursor key 以固定用途标签 HMAC 派生，不新增 Secret。
- Windows Survey 组合始终装配两个只读路由；只有完整 Document 证明依赖存在时，才装配三个写路由、
  Create/Validate/Submit Owner 和 Review 时允许全部合格项目成员重证的 PROJECT_RECORD Owner。
- 通用 PROJECT Review 组合在完整依赖下用唯一 Registry 同时注册 Handover、SurveyVersion 和
  SurveyConclusion；生产入口延后至 Document/Evidence 服务构造完成后再装配，避免半组合。

## 验证

- 定向单元/合同 7 项通过；完整依赖、部分依赖失败关闭、默认/只读/写路由均覆盖。
- Windows 11 / PostgreSQL 18.6：全新临时库执行真实 FastAPI 链，完成 VALIDATED Response、CLOSED
  Round、PROJECT_RECORD Evidence、Conclusion CREATE/LIST/GET/VALIDATE/SUBMIT_REVIEW、客户评审人
  APPROVE，并核对数据库 APPROVED 状态、SRV-05 Review、Audit 与 Alembic drift；临时库已清理。
- 后端全量 2942 项通过、3 项因既有 Windows 符号链接权限跳过。
- 开发 wheel 1105 entries，包含两项组合入口；SHA-256：
  `f86bb421db49d29539d6feeced8b3903b74572f8b11f75aad02f84e0cd0599df`。

## 兼容性、回滚与剩余项

无 Migration、ORM、冻结 API、依赖、Secret 数量、客户数据或网络外发变化。撤销三个组合入口改动即可
恢复 A02 默认关闭状态；已存在的 Conclusion、Review、Audit 和幂等历史不得删除。A04 前端、A05 真实
Edge、SUR-06 Workflow 资格、完整模拟项目、Windows Server 2025 发行复验、Gate 3/UAT 和可使用程序包
仍待；Debian 13 实机按用户指令跳过，不能据此宣称已实机验证。
