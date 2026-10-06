# CR-SUR-002：SurveyVersion 类型化来源证明适配

日期：2026-10-06。状态：依据 `CR-EXEC-001` 持续授权批准实施。

## 问题

Migration 0103 为 Survey 问题来源保存 Handover Item、Capability Item、TEMPLATE DocumentVersion 和
目标部门的类型化固定外键。现有 Handover/Capability 公共读取投影只暴露稳定业务 ID，不暴露版本内物理
row identity；Survey 若直接查询其他模块私有表，虽能填充外键，却违反冻结的 Owner 边界。仅依赖数据库
延迟触发器也不足以形成可测试、可替换的业务 Owner 证明。

## 选择

- 保留 0103 表结构、外键、冻结 `/api/v1` 与现有业务 ID，不改写 Gate 2 基线。
- 在 Handover、Capability、Project 各自模块新增最小、只读、caller-transaction 来源证明 Port/Adapter：
  只返回固定 row identity 及其已批准/可用/同 Project 事实，不返回正文、路径或额外客户数据。
- TEMPLATE 复用 Document 的 caller-transaction 固定版本证明，并额外要求类别为 `TEMPLATE`；GLOBAL
  模板仍按现有角色边界授权，不通过 Survey 绕过 Document Owner。
- Survey Service 先取得上述权威证明，再由 Survey Repository 写六表；数据库延迟触发器继续作为最终
  防御，不代替应用层 Owner。

## 实施拆分

1. `SUR-01-A03-P02-A01`：完成边界核查与本 CR。
2. `SUR-01-A03-P02-A02`：实现并验证 Handover/Capability/Project 最小来源证明 Adapter；不写 Survey。
3. `SUR-01-A03-P02-A03`：实现完整 DRAFT SurveyVersion 创建、规范化指纹、Audit/幂等和六表原子写。

## 风险、迁移与回滚

本调整不新增 Migration、外部依赖、网络、Secret 或数据外发。主要风险是把私有正文或非当前版本误暴露给
Survey；通过最小 dataclass、精确 ID/Scope/状态校验和负例测试关闭。撤销 Adapter 注册即可回滚代码；
0103 Schema 与已有 Survey identity 不受影响。真实客户资料、客户确认和 AI 外发均不在本 CR 范围。

## 验证计划

- 每个 Adapter 验证正确来源、跨 Project、非当前版本、未批准/不可用、停用部门及伪造组合。
- PostgreSQL 18.6 caller-transaction 证明和并发状态漂移失败关闭。
- A03 再验证完整六表、指纹、重放/冲突、Audit 回滚及零部分写入。
