# Job资源版本增量：CR-JOB-002

2026-09-27；原DM04/Schema冻结64cdf09保留，追加运行Schema0043，不追写原冻结历史。

JOB-01追加 `lock_version bigint NOT NULL DEFAULT 0 CHECK>=0`，用户乐观并发版本，不是JobAttempt/fencing或正式成果Version。数据库统一增量：实际任何Job字段变化计+1，唯lock_version（数据库owned）和lease_expires_at（纯续租）不作业务变化；直接改version、溢出拒绝，无变化不递增。原授权/actor/scope/Audit/不可变成果/终态历史不变。

API-01强ETag v<lock_version>可由后续GET准确提供；取消/重试必须在原所属Owner同事务锁定Job后比较expected_version再执行，不仅前端或请求前检查。当前命令尚未公开接线，此文不是If-Match已通过证据。

0042已有Job升级为0，新代码和Migration匹配门禁；备份恢复可信INSERT可以保留历史version。离线回滚丢版本并使客户端ETag无效，旧业务列/事件/Lease/结果保留。详见CR-JOB-002及job-01-a02-p01-resource-version进度验证，不外推生产部署/性能/Gate完成。
