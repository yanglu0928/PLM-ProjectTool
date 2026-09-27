# P07-A10-P02 Session当前来源真实验证

编码前检查2026-09-27：Phase2，WBS AUT-04-A12-P07-A10-P02；输入冻结64cdf09/0049/P01；前置现有真实隔离publication fixture及Session投影。涉及Auth User/Credential/Session与Project只读Application Port，无API/权限/Schema/生产/算法/依赖修改。

验收：实际PG当前Session成功、缺token/错误用户/无User拒绝；实际SQL当前行与三个不匹配fact字段拒绝；Project坏tuple/项/异常不返回投影；实际reset生成受限Credential后投影隐藏角色/项目且不调用Project；成功/拒绝前后十二业务表SELECT全行不变。重复成员按下述实测修正，不要求移除约束造成功SQL。

证据边界：坏fact由真实读取结果替换字段，仅证明当前SQL与传入fact错配防御，不称数据库真实损坏。Project坏Port故障注入明确标注。License仅合成、角色fixture明确TEST_ONLY，临时DB/文件/Vault由原fixture限定所有权创建清理，不动生产或客户资料。

首次真实执行：其他断言走到末尾，第二活跃成员INSERT被uq_prj_members__user_active拒绝，exit1；原fixture finally清理owned资源。验收计划错误，不是生产投影缺陷。修正为核对实际UniqueViolation约束名、十二表不变及原投影健康，保留来源len>1分支未覆盖事实，不移除约束/伪造成功SQL。

风险/回滚：新增验证入口，不改生产；撤入口无升级。原publication回归同轮执行，unit最近1480本批不重跑；coverage/性能/wheel未跑，不推算覆盖或关闭Gate/CR008/完整包。原raw/Hash保留。

重跑结果：exit0；实际PG健康投影/缺token/错用户/无User拒绝、三fact错配与三Project坏Port拒绝；实际reset受限投影不调用Project。实际UniqueViolation精确约束名确认，原健康投影保留。每次投影与失败INSERT十二表全行不变；原dualScope空/260行publication实际回归通过。仅已列行为通过，Project len>1分支未覆盖，不豁免剩余安全验收。下一P07-A11保持完整Auth范围/原90%与独立新runtime，1480unit+原11链+本入口共12链统一覆盖实测。
