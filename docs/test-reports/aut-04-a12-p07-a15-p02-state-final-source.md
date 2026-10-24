# P07-A15-P02 自停用最终来源与真实回滚

2026-09-27 Windows11/Python3.13.15/隔离PG18/current0049；实际入口validation/aut-04-a12-p07-a15-p02-state-final-source/verify.py，exit0。

实际缺User Repo RESOURCE_NOT_FOUND、九表不变。八种final故障均先调用原actual final取得True；再缺Session token/到期idle时间/credential-proof/CSRF明确输入故障，同UOW实际User版本增/插入活Session/其他Admin停用，以及实际SQL22012中止后25P02异常。原final拒绝False→Service AUTH_ACCESS_DENIED；中止事务→Service AUTH_STATE_UNAVAILABLE。

八次User/Credential/Session/create-first/state-first/change-first/reset-first/Audit/Receipt九表SELECT全部行与前完全相同；旧Session实际validate可用。未禁触发器/模拟SQL成功。随后真正正常self-disable提交：User DISABLED、revoked_count1、原Session USER_DISABLED。原dualScope空/260行文件/publication回归同轮通过。

角色设置仅TEST_ONLY/License合成；资源原fixture限定所有权清理，非生产信任或目标账户证明。生产/Migration/API/权限/算法/依赖无变化。unit1501为最近结果本批未跑，coverage/wheel/性能未跑，旧Auth82.186%与Hash保留；下一完整14链统一实测，90%/性能CR008 FAIL/正式trust/Gate3/可用包未关闭。
