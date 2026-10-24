# P07-A14 用户状态Service防御结果

2026-09-27；Windows11/Python3.13.15；新增6参数化方法，全量1497unit failures0/errors0/skipped2，exit0。

|类别|案例|结果|
|---|---|---|
|必需依赖|7|构造拒绝，无UOW|
|clock/ActorProof|6|reserve/写前拒绝|
|收据/first引用|4|无Repo写/Audit/complete|
|change返回view/state/version/count|8|Audit/record前拒绝|
|first归属/操作/版本/内容与Audit|5|complete前拒绝|
|最终proof改变|1|complete后拒绝，不commit|

已进入UOW均正常退出，无commit；Mock只Port合同控制，不表示SQL回滚成功。已有enable/disable正向、self-disable exact True与实际Windows原链保留，生产/Schema/API/权限/算法/依赖均无变化。

coverage/13PG/wheel/性能本批未跑，原A11完整Auth82.186%分支/Hasha2fb0a38…保留，不推算提升；正式trust/性能CR008 FAIL/Gate3/可用程序包未完成。下一独立User状态Access/Repo前SQL与实际来源验证，再统一同范围覆盖。
