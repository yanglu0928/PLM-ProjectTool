# CAP-01-A05-A02：Capability 当前受权读取 Owner 与游标

日期：2026-10-05。结论：`CAP_01_A05_A02_READ_OWNER_PASS`。下一项：`CAP-01-A05-A03` Capability 状态 Owner 与 Schema0095。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A02
输入基线：冻结API-01/API-04、DM-05、Schema0094、CR-CAP-001、DEC-840
前置任务：Capability Baseline/Draft/Validate/Review正式化与A05前置核查已通过
涉及模块：capability application/infrastructure/api；auth/project只读Port
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem、DocumentVersionRef、EvidenceRef
涉及API：本项不挂HTTP；为五个冻结GET准备内部Owner和分页位置
涉及权限：DeploymentAdmin受控全历史；当前ACTIVE项目成员只读ACTIVE基线当前APPROVED投影
验收标准：Session/User/License/Project事实重验，跨状态隐藏，稳定分页，游标Session/权限/查询/资源族绑定
风险：GLOBAL Draft泄漏、停用成员继续读取、跨游标族重放、来源引用顺序漂移、异常细节泄漏
```

## 实现与决策

新增统一只读服务与三类安全DTO，五个查询均先重验License、当前Session和启用User。DeploymentAdmin进入`ADMIN_HISTORY`；非管理员必须由Project模块证明至少存在一个ACTIVE Project、ACTIVE Department和当前ACTIVE Member，才进入`CURRENT_APPROVED`。普通成员的Baseline查询在数据库层限定ACTIVE且有正式指针，Version/Item查询再限定该指针指向的APPROVED Version；因此Draft、IN_REVIEW、RETURNED、SUPERSEDED、RESTRICTED和归档基线均按不存在处理。

Project成员证明由Project模块持有，Capability不直查Project表；Capability仓储只投影本模块五表，并按固定ordinal返回DocumentVersion/Evidence引用。详情缺失和无权限历史均收敛为`RESOURCE_NOT_FOUND`，基础设施异常收敛为`CAPABILITY_UNAVAILABLE`，不向上泄漏SQL或身份细节。

分页采用两个独立32字节HMAC密钥域：Baseline游标独立一域，Version/Item子资源游标使用同一Capability子域但严格绑定不同family。两者均绑定Session摘要、权限投影、page size；子游标另绑定Baseline或Version scope，拒绝跨用户、跨投影、跨查询、跨资源族和篡改重放。HTTP Router和目标账户密钥读取留在A05-A06/A07，本项不引入Secret或默认密钥。

## 验证

- Windows 11 / PostgreSQL 18.6隔离库：复用完整Capability四版本正式化场景，DeploymentAdmin读到APPROVED/RETURNED/RETURNED/SUPERSEDED全历史；ACTIVE项目成员只读当前APPROVED及其Item；读取旧SUPERSEDED返回`RESOURCE_NOT_FOUND`；无项目成员关系用户被拒绝。空库迁移/drift及Schema0094终态回归同时通过，临时库清理。
- 新增13项定向单测覆盖两种投影、无成员/无Session/禁用用户、License、分页、仓储形态失败关闭及两个签名游标的全部绑定；后端全量2572项通过、3项既有条件跳过。
- 开发wheel内36项Capability测试通过，SHA-256 `824642fbec46d94050047da4b73a190fd2e3e28d9495e8caabc26960b81f7f70`；`compileall`与`git diff --check`通过。

## 兼容、回滚与剩余边界

无Schema、Migration、冻结API、依赖、网络、外发、Secret或客户数据变化。停止装配读取服务即可关闭新能力，数据库历史不变；后续HTTP未提供密钥时必须拒绝启动，不能退化为无签名分页。

本项没有挂载五个GET，未证明真实HTTP、目标账户游标密钥、前端、Server2025、性能或正式信任。A05-A03状态Owner、A04～A07及Gate 3/发行仍未完成。
