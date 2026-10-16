# AUT-04-A12-P07-A04：Service违约边界第一批

2026-09-27；0.1.0.dev0；A04-P01_PREPARATION_DEFENSIVE_TESTS_PASS / A04_REMAINING_BOUNDARIES_PENDING。Phase2；输入ccfa0cc/0049/冻结64cdf09、P07A03覆盖缺口；前置满足。仅reset/change Service测试，不改生产实体/API/权限/Schema/算法/依赖。上一轮HTTP与真实集成补测已推送，属于进展。

本批验收：缺依赖、错误历史hint类型/操作/status、first ID错配、source DTO违约及非可信时间在昂贵KDF/写入前拒绝；不得reserve/调用repo/commit，所有密码擦除。测试替身只证明Service消费Port时防御，不伪称实际SQL回滚；真实PG依据P07A03保留。完整unit重跑，本批不重跑四组PG或推算新覆盖率，不覆盖旧报告/Hash；下一剩余写后repo/result/final-proof边界及统一实际集成覆盖复验。

风险/回滚：不得删路径或降90%门槛提高分数，局部通过不关闭安全/Gate。撤测试即回滚，生产无升级。性能CR008仍FAIL/默认4，正式信任/目标环境与完整可用包未完成。

执行：新增6个参数化方法覆盖reset9/change8个缺依赖、reset6/change7个错误历史坐标/source/actor、两类各4个非法时间；准备UOW均闭合，明确保留每个tx并断言commit未调用，reserve/repo/global/KDF未调用与密码擦除。完整1447unit最终无失败/errors0/2既有跳过，实际重跑已含强化commit断言；无生产实现变化。

首次新测试中两项错误operation字符串自身不符合IdempotencyResult格式，在调用Service前被DTO拒绝，不是所需Service证据。已修成另一个真实合法operation再测试，未修改生产校验；全量重测通过，历史错误如实保留。本批未执行coverage/四实际PG/wheel，不推算新百分比，P07A03原密码分支79.189%证据保持且未覆盖原JSON。完整A04尚未完成：下一A04-P02写阶段repo/result/current-final-proof违约与无commit/擦除，随后独立真实PG完整覆盖复验。90%门槛/性能/Gate/包未关闭。
