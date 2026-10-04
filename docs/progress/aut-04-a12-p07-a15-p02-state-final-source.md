# P07-A15-P02 自停用最终授权真实来源

2026-09-27编码前检查：Phase2/WBS AUT-04-A12-P07-A15-P02；输入冻结64cdf09/0049/P01；前置真实owned PG/Vault/publication与User状态Service。Auth User/Session/Proof/first/Audit/收据最终来源；无生产/API/权限/Schema/算法/依赖变。

验收：实际缺User Repo拒绝；真实self-disable Service写后final先True，再缺Session/过期时间/credential-proof/CSRF/User版本/新活Session/其他Admin失效/SQL22012中止各拒绝，九表全行回滚、旧Session仍可用；最后无故障正常self-disable提交。DTO/time/CSRF故障显式注入、User/Session/其他Admin故障实际同UOW SQL；不mock成功SQL、不禁触发器。

风险/回滚：测试Admin角色仅TEST_ONLY隔离设置，License合成，不生产供给证明；原fixture负责owned资源清理，无客户数据/生产操作。新增验证可撤，无升级；原publication同轮回归。unit最近1501本批不跑，coverage/14链/wheel/性能未跑，旧raw/Hash/90%保持，正式trust/CR008/Gate/可用包待。

结果exit0：实际缺User RESOURCE_NOT_FOUND/九表不变；八次真实Service final先True，缺Session/idle边界/credential-proof/CSRF/User版本/活Session/其他Admin拒绝，SQL22012后原final实际25P02→Service固定AUTH_STATE_UNAVAILABLE。八次九表SELECT全部行精确回滚，原Session validate仍可用；随后真实无故障self-disable提交、revoked_count1/原Session USER_DISABLED。原dualScope空/260publication回归同轮通过；生产无变化，unit1501本批未跑、coverage/性能/wheel未跑。下一P07-A16完整unit与原12+创建Result+state-final共14链同轮完整Auth覆盖，独立runtime保历史，不推算当前比例/关闭Gate或完整包。
