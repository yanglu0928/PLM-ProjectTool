# PLT-PKG-01-A09-P51-A13：逻辑恢复后的外键完整性审计

日期：2026-10-26。状态：`PASS_SCOPE_LIMITED_POST_RESTORE_FK_AUDIT`（Windows 11非发行候选；仅合成隔离数据）。

## 编码前检查

|项目|结论|
|---|---|
|当前Phase/WBS|Phase 2 / `PLT-PKG-01-A09-P51-A13`|
|输入基线|`CR-EXEC-002`；固定候选SHA-256 `3cbd68aaad08b111fdf809575915358d7d7737a266990ed6bd3df23f2326f455`；A11逻辑恢复与A12同Session恢复库API读取限定证据|
|唯一问题|P51-A05合成Prototype验收所用RequirementVersion写入随机占位`review_ref`/`review_round_ref`，且数据库存在循环外键（例如用户/凭据），使data-only restore不能全程启用触发器；能否建立主体匹配的合成Review关联，并在装载后独立反连接审计所有plm外键，补足实际引用完整性证据|
|涉及模块/实体|仅一次性`validation/plt-pkg-01-a09-p51-a05-prototype-packaged/verify.py`测试数据fixture、A11恢复后只读FK审计及一次性验收器；不改产品代码、ORM、Migration、API、数据库约束或发布包|
|初步依据|RequirementVersion ORM的`review_ref`与`review_round_ref`允许同时为空，但Prototype候选查询要求当前Approved RequirementVersion具备非空评审指针；A13失败复验已证实NULL方案导致Prototype版本创建HTTP 404，故不得采用NULL伪装合格。`RequirementReviewSubjectOwner.SUBJECT_TYPE=REQ-03`，Review主体应指向Requirement ID，轮次`subject_version_id`应指向RequirementVersion ID。|
|范围/权限|仅当前smoke新建的合成数据库与随机目标库；不得触碰客户/生产数据、正式Credential Manager目标、产品表结构或现有工作区的其他夹具数据。所有操作绑定当前run拥有的连接和资源。|
|验收标准|候选完整Edge/HTTPS/PG链通过；A05 Prototype仍达到原既定行为，合成Requirement Review主体指向Requirement、ReviewRound版本指向RequirementVersion；保留循环外键restore兼容选项后，逐项反连接检查恢复库所有plm外键且违规为0；Plan/Audit/收据/Review数据对比、迁移head、候选SHA、临时资源清理均通过。|
|风险|NULL试验已暴露Prototype资格查询要求Review指针，HTTP 404后已通过主体匹配合成Review修正；全程启用触发器又暴露用户/凭据循环FK的恢复顺序问题。最终仍可能检测到其他既有夹具关系违规；若有，则保留结果、不得忽略或删除源数据，A11/A12限定结果保持有效。A13不证明真实客户数据库灾备、异机/RTO/RPO、正式安装、Pilot或Release。|

## 实施与回退

- 先确认P51-A05是隔离合成验证，不把种子作为客户事实；Review记录标记为测试夹具且不伪称人工/客户批准。创建Review时须与Requirement/Version主体身份一致，并遵守Review表状态约束；若需伪造decision/audit或绕过Schema约束才能通过，则停止本方案。
- 计划差异（编码前记录）：先试用Schema允许的`NULL/NULL`并保留A11 FK触发器；A13完整浏览器链在Prototype创建端点返回404，证明业务查询要求非空评审指针。建立主体匹配的合成`REQ-03` Review/ReviewRound后，Prototype浏览器链通过；但保留触发器的data-only恢复在用户/凭据循环FK处因恢复排序失败。最终修订为保留PG要求的`--disable-triggers`恢复顺序，再在恢复完成后对每个plm FK独立执行按键反连接审计；若违规不为0则失败关闭。此项不关闭约束、也不改变冻结基线。
- A13验收器确认目标库合成Requirement Review/ReviewRound主体及版本一致、所有plm外键无孤儿引用、关键业务数据一致。
- 回退仅撤销测试验证器和测试fixture调整，固定候选/产品Schema/业务数据不变；原A11/A12证据继续有效且保留。

## 验证计划

- P51 smoke定向单测、语法/diff检查；核对候选stage及固定SHA。
- 包内完整Edge/HTTPS/隔离PG链和A13只读反连接审计；恢复阶段使用`--disable-triggers`以处理循环外键，单独核验最终数据关系完整。
- 复查临时PG/API/Caddy进程、目录、备份及Vault目标清理；secret扫描后同步到`feature/license-runtime-guard`。任何失败保留日志中的非敏感诊断并另找不受影响任务。

本项没有产品基线、业务事实、API、Schema、依赖或许可协议变化；验证通过也只表示当前Windows 11合成测试夹具的数据约束恢复路径成立。

## 首轮失败证据

- NULL/NULL Requirement引用候选使Prototype版本创建返回404；不符合业务资格查询，已弃用。
- 主体匹配Review/ReviewRound夹具后，P51-A05真实Edge Prototype链通过；全程开启FK触发器的恢复则因用户/凭据循环FK按插入序失败（`auth_password_credentials`先于其`auth_users`记录插入）。这提示恢复排序而非必然源孤儿；原错误只记录表/约束/随机ID，不含密码摘要/凭据内容。

## 最终验收结果（2026-10-26）

- 完整候选Edge/HTTPS/隔离PG链通过，P51-A05 Prototype真实浏览器链在主体匹配的合成`REQ-03` Review/ReviewRound夹具下成功；目标恢复后对`plm` schema全部外键执行逐约束只读anti-join，违规数为0，输出`P51_A13_FK_DATA_AUDIT_PASS`。A11 Plan/Audit/收据/Review计数和Migration head检查通过。
- 为兼容PG18用户与密码凭据循环外键的data-only恢复顺序，保留`--disable-triggers`完成装载；不声称恢复期间触发器开启。完成装载后不是只检查`convalidated`元数据，而是按每一条FK真实查询子表非空键且`NOT EXISTS`父表的孤儿行；发现任何一条即失败。MATCH SIMPLE/FULL均按其空值语义处理，不支持的FK形状失败关闭。
- A12同一Session读取恢复库并精确恢复Credential Manager连接的回归也通过：API重启2次、PG重启1次、逻辑恢复1次，候选SHA不变，临时进程/文件/PG/Vault/布局清理均通过。A12专用runner跳过Prototype UI重复探针但重新建立相同主体一致的合成Requirement/Review夹具；本A13全链另实际运行Prototype Edge并通过。
- 单测8/8、语法与diff检查通过；不改产品代码/API/Schema/Migration/依赖，仅修正测试夹具Review关系并扩展一次性验收器的恢复后FK审计。限制：只证明当前Windows 11候选合成数据的关系完整性，不代表真实客户数据、正式灾备、RTO/RPO、安装/Pilot/Gate/发行或其他平台。
