# SOL-05-A04-P11-P04-P01：显式 NONE_REQUIRED 写 Owner

日期/版本：2026-10-23 / `0.1.0-dev.0`。状态：`WINDOWS_INTERNAL_PASS`；仅限有界人工理由的声明，新固定 Spec 引用仍关闭。

## 编码前检查与范围

前置以 `docs/progress/sol-05-a04-p11-p04-section-spec-owner-precheck.md` 和 `DEC-20261023-1203` 为准：Phase 2、Gate 2 冻结 API-04/DM-05、CR-SOL-022、0178 闭锁 Schema、P11-P03 兼容输入/读取均已满足。本片只修改 Solution SectionVersion 的人工 `NONE_REQUIRED` 写入；不修改路径、角色/权限、License、SpecVersion/Review、前端或客户业务事实。验收为理由进入不可变版本和请求/内容指纹，同事务收据/Audit/首响，旧请求/旧首响稳定，固定引用继续闭锁，空/旧数据升降及实际 Win11/PG/HTTP 负例。风险为把“无需专项”误称客户确认、把裸 Spec UUID 误认为适用、或用新字段破坏旧 Key 回放。

## 实施与验证

- 新迁移 `0179` 仅将 `0178` 根 Guard 开放 `UNDECLARED` 或 `NONE_REQUIRED`、零 Spec 引用；固定引用表的 DML/TRUNCATE 仍全闭锁。数据库 Check 保证理由非空、规范化、有界。已有声明/引用历史时禁止降回 `0178`，否则可恢复原闭锁函数。ORM 字段与检查沿用已验 `0178`，无新 Schema 漂移。
- 受权 CREATE 只对 `FIXED_REFS` 继续失败关闭；输入证明仍复用真实 Document/Requirement/Evidence 当前来源，内容指纹包含含理由的请求指纹。Repository 在同事务写根的状态/理由/零计数及既有 Requirement/Evidence/不可变首响；Audit 与持久幂等收据同事务。旧 201 形状不变，声明由受权历史 GET/DETAIL 读取；明确理由不能替代客户 Review。
- 定向 17 项/25 子例通过；完整后端 `3894 passed, 3 skipped, 6038 subtests passed`。Win11 一次性 PG18.6 真实 Auth/Project/Document/Requirement/Evidence/HTTP：新声明 201、同 Key 首次响应回放、改理由 409、FIXED_REFS 503、非法理由 422、跨项目隐藏、DB 根理由/计数与 ORM 反读、只新增一条版本/收据/Audit、非空声明拒降通过；旧 Section CREATE/来源撤销/并发验证重放退出 0。原 P11-P02 空/旧数据升降与 Alembic drift 在 head 0179 复跑退出 0。

兼容与回滚：旧客户端请求与首次结果保持；0179 对旧数据无回填。若出现新 NONE_REQUIRED 历史，不能降级或删史，应关闭新增入口并前滚修复。已知问题：`FIXED_REFS` 的 SpecVersion 同项目/适用性/Review 资格与封闭集合 Owner 仍待 `P04-P02`；Section/Outline Review、Pilot 安装/正式信任、Gate 3 和发行未通过。
