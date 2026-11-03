# CR-PLG-009：PluginInstallation运行时兼容性重验证与失败关闭

- 日期：2026-11-04
- 状态：编码前登记；按持续自主授权实施，依据托管证据验收
- WBS：PLG-02-A04
- 基线：冻结Data Model V1、DB Schema V1、API Contract V1、CR-PLG-007/008

## 原因

PLG-02-A02只存首次兼容事实，A03激活要求最新兼容快照，但没有运行环境重验证Owner。冻结模型要求兼容失效时停止新的PluginExecution并保留既有OutputArtifact。

## 决定与范围

- 新增内部重验证Owner，通过受控安装证据端口核对Installation存在、精确Package ID/SHA和runtime快照。
- Migration 0228允许经Owner受限更新Installation的兼容快照/状态。每次真实有效复验都追加新的RuntimeValidation和Audit，并把Installation、Audit及operation现态/history在同一事务提交；没有请求幂等键，不以相同快照跳过审计。expected_lock_version拒绝陈旧写入。
- COMPATIBLE时保留合法启用；从INCOMPATIBLE恢复时转DISABLED并须重新启用。INCOMPATIBLE时清空全部启用操作，按operation追加DISABLED history/Audit，标记Installation INCOMPATIBLE。
- 保持RuntimeValidation/history只追加，Owner外写入/TRUNCATE拒绝；不新增实体/API/依赖/默认组合。
- 不物理安装或卸载，不启动插件，不删除既有产物。人工disable/retire终态入口不混入A04。

## 风险与回滚

- 并发激活/复验、摘要不匹配、历史保留和同事务一致性是主要风险；以plugin级锁、expected lock_version、包SHA及UoW控制。
- 只增加0228，不重写旧Migration。空库upgrade/down/re-upgrade须通过；存在相关PLG-02事实/operation history则down失败关闭，保留所有数据。
- 不改变冻结状态/API，不产生数据转换或外部调用。发现额外偏差先写本CR再改。

## 托管验收

- GitHub hosted Windows runner D:临时目录：定向Owner反例、后端全量/wheel、ORM/Migration contract、PG18空库和合成有数据升级/降级、完整父包与A17/A34/A35/A50链。
- 客户数据0、外部API0、生产数据库false；不得本机/C盘跑项目代码或测试。
- 只有证据通过后结论为`PASS_SCOPE_LIMITED`；不等于设备兼容、正式信任、PluginExecution、Pilot/Gate/Release。

按用户持续自主执行授权先行登记实施范围、风险、迁移、回滚和验证计划。


## 托管验证偏差记录（2026-11-04）

首次完整父包 PostgreSQL smoke 在校验“带 PLG-02 历史禁止降级”时失败关闭。迁移 0228 实际返回 `PluginInstallation runtime history prevents downgrade`；既有 migration verifier 仍期待 0225/0226 时的旧文案 `PluginInstallation history prevents downgrade`。这是验证器断言文本未随 0228 的错误信息更新，不是迁移放行或运行历史丢失。数据库 smoke 随后按失败路径停止；不记录本轮完整验收通过。

处置：先保留迁移保护和当前错误文案，只修正 verifier 精确断言以对应 0228 的保护结果，随后重跑同一 hosted 全链。风险为验证语义误报；不会改数据库状态、数据、API 或插件运行行为。回滚方式为恢复旧 verifier 断言，Migration 0228 无需回滚。验证仍要求有历史时拒绝降级并保持 schema revision/history 完整。
