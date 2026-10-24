# SOL-05-A02-P10：SectionVersion INSERT-only Guard 0160 增量

日期：2026-10-09。依据冻结 Gate2 DM-05/API-04、CR-SOL-003/P07～P09；原冻结提交 `64cdf09`、0138/0159 历史文件不改写。

`20261009_0160` 在四张 SectionVersion/固定 Requirement/Evidence/首次响应表均空的前提下，替换原全拒写函数为 INSERT-only Guard，并给版本根加可延迟到事务提交的闭环触发器。版本插入按 Outline→Section 顺序锁定活动父行，限定同 Project、DRAFT/无 Review、仅 DocumentVersion 正文、声明数组上限/元素对象和连续版本号/前驱；子引用限定父版本及声明数量，原唯一约束和复合 FK 继续约束目标与 ordinal。首次响应插入核对版本/Section/Project、标题、正文、指纹、声明、计数、前驱、创建人/时间的完整一致性。延迟触发器在事务结束检查固定引用数量、1～N 连续 ordinal 与首次响应存在；缺任一部分则整事务回滚。

所有四表 UPDATE/DELETE 与 TRUNCATE 仍拒绝。此数据库 Guard 不证明 Document 物理字节、Requirement 当前批准、Evidence 当前资格、调用者 Session/License/Project 授权或 Audit；这些必须由下一 P11 的同事务业务 Owner 证明。Artifact/Spec 分支继续关闭，不能把 SQL INSERT 可行误称正式 CREATE 功能已上线。数据库账户仍须按部署基线隔离，不能将直接 SQL 写入口交给终端用户。

迁移/回滚：已有 Project/Outline/Section、Document 等数据保留不回填；若四张新历史表非空，升级前停止并走独立审计迁移。空表可 0159→0160→0159→0160；任何版本/子引用/首响应有历史即拒绝降级，不能清除正式数据规避门禁。实际生产升级仍要求备份、账户/权限和恢复演练。

验证：`validation/sol-05-a02-p10-section-version-create-guard/verify.py` 在 Windows 11 一次性 PostgreSQL 18.6 验证空/既有 Section 数据升降重升、drift、Artifact/跳号拒绝、缺首次响应或缺固定引用回滚、结果不匹配拒绝、Document 分支零引用及一 Requirement/Evidence 正常原子提交、四表历史不可改/删/截断和非空拒降。正式 Server2025、目标服务账户、P11 真正 Owner/HTTP 与 Gate3/发行仍未验；Debian13 实机按用户指令跳过。
