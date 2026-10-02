# CR-AI-010：AITask 输入版本补全业务对象身份

日期：2026-10-02；状态：依 V1.1 持续授权登记，0065已实施并完成Win11隔离验证；Owner注册与内部Task创建待后续；关联冻结 API-01/03 `ResourceVersionRef`、DM-04、Schema0063及 DEC-698/699；原 Gate 2 冻结提交 `64cdf09` 和0063历史不改。WBS `AI-04-A03`。

冲突与证据：冻结公开输入版本引用必须包含 `resource_type`、`resource_id`、`version_id`，Owner解析后还需保留 Owner/ObjectType/Scope/Project。0063 `ai_task_input_refs` 已保存 Owner/ObjectType/VersionId/Scope/Project，但遗漏业务 `object_id`。仅凭版本UUID即使当前物理表中唯一，也不能完整重建客户端三字段引用、证明对象与版本归属或适配不同Owner的复合身份；若直接把 `version_id` 当 `object_id` 会伪造业务事实。

方案比较：A 假定所有Owner的ObjectId等于VersionId，违反冻结模型，否决。B 修改冻结API删除ResourceId，属于Breaking Change且削弱追溯，否决。C 以0065为输入引用增加可空 `object_id`，新插入由数据库守卫强制非空并由Owner Port同事务证明；0063既有行保持NULL、不可改写且不得用于新执行/重试，选择C。

差异与风险：最终新引用完整保存 Owner/ObjectType/ObjectId/VersionId；为兼容0063历史，物理列暂允许NULL，但只限迁移前遗留行。应用层必须把NULL视为 `AI_INPUT_REFERENCE_UNRESOLVED` 并失败关闭，不能猜测回填。风险包括遗留Task被误执行、跨项目引用和回滚丢失新身份；通过插入守卫、Owner注册白名单、同事务Scope/Project证明、读取失败关闭与有新身份时拒绝降级控制。

迁移/回滚：新增0065/ORM；空库与既有0063数据均可升级。既有NULL历史保持只读。若没有任何非NULL新身份可降0064；存在新引用时拒绝物理降级并向前修复或受控备份恢复。不得更新0063遗留InputRef来伪造历史。

验证计划：P01登记差异；P02验证空库及既有NULL历史升级、drift、新插入缺ObjectId拒绝、完整身份不可变/Scope同Task、遗留行保持NULL、空/仅遗留可降重升、非NULL新历史拒降、后端回归和wheel；P03以后再实现显式Owner注册及内部AITask创建。无真实数据外发、API开放或生产迁移。

P02结果：ORM/Migration0065已实施；Win11隔离PG18空库和仅0063遗留NULL历史升/降/重升、drift=0、新写缺ObjectId/零UUID/跨项目拒绝、完整身份改删拒绝、遗留NULL不改写及非NULL新历史拒降全部PASS。首轮测试把公开`DOC-02`误作Owner内部ObjectType而被既有白名单正确拒绝，改为解析后`DOCUMENT_VERSION`并完整重跑。后端2100运行/3跳过PASS；开发wheel SHA-256 `b0cd5c1288cb2ac278d755068124245b858270a2bd2a6cc53d06a864da7ab7ca`。无真实外发/API/生产迁移。
