# P07-A10-P02 真实Session投影来源

2026-09-27 Windows11/Python3.13.15/隔离PG18/current0049；入口validation/aut-04-a12-p07-a10-p02-session-source/verify.py。

首次exit1：实际唯一约束阻止第二活跃成员，计划假设错误；未删除约束或绕过数据库，owned fixture清理。修改验证计划后重跑exit0。

通过：实际Session原项目投影、缺token/错误用户/无User拒绝；实际当前SQL与三字段错配fact拒绝（明确DTO故障注入）；Project坏list/坏项/异常拒绝（明确Port故障注入）；实际reset与issue产生受限Credential投影无Project/角色NONE；实际第二活跃成员INSERT失败约束名精确匹配，原健康投影保持。

每次投影与失败INSERT前后十二业务表SELECT全行一致；原publication双Scope空/260行、实际文件/Vault/当前User/Lease/多类故障回归同轮通过。临时资源由原fixture正常清理，无生产或客户数据操作。

Project len>1分支没有执行，不豁免；正向License合成、非生产trust/目标账户证明。完整unit1480为P01最近结果，本轮未重跑；coverage/性能/wheel未跑。下一完整12链+unit独立runtime实测，不推算全Auth覆盖、Gate或交付完成。
