# PLT-PKG-01-A09-P51-A13：触发器启用的逻辑恢复完整性前置

日期：2026-10-26。状态：`PRECHECK_READY`（Windows 11非发行候选；仅合成隔离数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A13`|
|输入基线|`CR-EXEC-002`；固定候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；A11逻辑恢复与A12同Session恢复库API读取限定证据|
|唯一问题|P51-A05合成Prototype验收所用RequirementVersion写入随机占位`review_ref`/`review_round_ref`，导致A11只能在data-only恢复期间禁用触发器；能否纠正测试夹具，使空值语义符合Schema并在恢复期间保持约束/触发器启用，从而补充验证恢复数据的引用完整性|
|涉及模块/实体|仅一次性`validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py`测试数据fixture、A11逻辑恢复参数及一次性A13验收器；不改产品代码、ORM、Migration、API、数据库约束或发布包|
|初步依据|RequirementVersion ORM的`review_ref`与`review_round_ref`允许同时为空，并以CheckConstraint要求二者同时NULL或同时非NULL；A05合成Requirement仅作为Prototype输入。须复查查询/验证路径确实不依赖该伪造评审引用，并在正式实施前加断言。|
|范围/权限|仅当前smoke新建的合成数据库与随机目标库；不得触碰客户/生产数据、正式Credential Manager目标、产品表结构或现有工作区的其他夹具数据。所有操作绑定当前run拥有的连接和资源。|
|验收标准|候选完整Edge/HTTPS/PG链通过；A05 Prototype仍达到原既定行为且数据库中合成RequirementVersion的评审引用均为NULL；使用`pg_restore --data-only`恢复时不使用`--disable-triggers`；恢复后显式查询受影响引用并运行受限FK验证；Plan/Audit/收据/Review数据对比、迁移head、候选SHA、临时资源清理均通过。|
|风险|测试夹具修订可能暴露Prototype流程对“已批准Requirement”的真实依赖；若Prototype失败或requirement来源断言改变，不得用空值掩盖业务缺口，停止该尝试并保留A11/A12结果。A13不证明真实客户数据库灾备、异机/RTO/RPO、正式安装、Pilot或Release。|

## 实施与回退

- 先确认A05 Prototype流程读取该RequirementVersion时只依赖批准状态、内容与验收标准，不依赖Review/ReviewRound关系；若依赖则不改造测试事实，转记录阻塞/重新评估。Schema明示两个Review引用可同时为空，测试fixture禁止用随机孤儿UUID冒充Review事实。
- 完成检查后，先在本记录追加实施差异、风险和回滚说明，再改A05测试fixture将两个引用设为NULL，并更新A11恢复命令删除`--disable-triggers`。新增A13只读验收器确认目标库引用为空、相关约束有效且可验证，且关键业务数据一致。
- 回退仅撤销测试验证器和测试fixture调整，固定候选/产品Schema/业务数据不变；原A11/A12证据继续有效且保留。

## 验证计划

- P51 smoke定向单测、语法/diff检查；核对候选stage及固定SHA。
- 包内完整Edge/HTTPS/隔离PG链和A13查询；确认恢复时启用触发器且无孤儿Review引用。
- 复查临时PG/API/Caddy进程、目录、备份及Vault目标清理；secret扫描后同步到`feature/license-runtime-guard`。任何失败保留日志中的非敏感诊断并另找不受影响任务。

本项没有产品基线、业务事实、API、Schema、依赖或许可协议变化；验证通过也只表示当前Windows 11合成测试夹具的数据约束恢复路径成立。
