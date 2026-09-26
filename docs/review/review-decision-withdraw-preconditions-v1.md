# Review 决定/撤回与 Owner 终态消费前置 V1

日期：2026-09-26；WBS：RVW-02-A06。输入：AF-02、DM-02、API-02、CR-RVW-001、0034、RVW-02-A05。本文件及内部 DTO/Port 不代表实际业务批准或身份锁已验证。

## 命令与当前权限

决定 Actor 必须来自当前有效 Session/CSRF，License 和 ACTIVE Project 当前成员资格通过，并为固定本轮 assigned reviewer；实际 Subject Owner 按冻结 policy 再验具体确认权。PM 不能替其他 reviewer 决定；部署管理员没有 PROJECT 旁路。API-02 decide 无 M 控制，不新增 If-Match 必填；root/round 行锁与唯一 Assignment/Decision 序列化。撤回仅当前 PM，沿用 Review 强 ETag/If-Match 与持久幂等，不以 Round 内部计数替代根版本。

新 Key 不覆盖已经最终决定；成功收据重放返回不可变首次结果，先重验当前 Session/CSRF/License/Project 与固定历史版本访问权，不重新执行批准或锁释放。资格后来改变不篡改旧决定，但不能绕过当前访问权。首次 RETURN comment 必填；全部 assigned reviewer 完成才终结，首条 RETURN 保持真实主题锁。

## 单步交接合同

`ReviewSubjectTransition` 绑定当前可信固定 Round 快照、Actor、Trace、UTC 时间以及一次精确追加决定或撤回后的完整进度。拒绝更换 Round/确认人、重写历史、代理决定、终态再写与计数溢出。仅 PROJECT 内部入口；不把 GLOBAL 混为项目。DTO 构造与比对只能检查形状和关联，不能证明当前权限、Sources 或 Owner 实际锁。

授权/锁核验 Port 不提供默认实现，成功只能返回 None，异常失败关闭。调用方需要严格检查返回值，拒绝 True/UUID 替代真实操作。终态消费只接受 terminal intent；非终态不得释放身份锁。

RVW-02-A08 内部实现另要求消费后独立 `assert_terminal_consumed_in_transaction` 重读实际消费/正式指针/身份锁释放事实，不能把 None 响应当事实证明。owned 根独占锁后复用固定 Round 共享读再交接 Owner 的实际读锁序记录于 DEC-20260926-182；真实 Owner 接入前必须检查交叉锁序和并发，不以合成事务标记替代业务锁。

## 同事务终态消费

选择模块化单体同一业务事务内同步消费 ReviewCompleted，不选择异步 best-effort 通知。Review owned 状态/历史、Owner 消费与正式版本指针/实际身份锁释放、Audit、receipt 同事务 commit；任何一步失败连最终决定一起 rollback。Review 不写 Owner 表，Owner 只通过公开内部 Port 消费结果。没有实际 Owner 就不执行该写路径。

APPROVED 消费必须重验固定 Version 内容与送审 fingerprint 一致、必要 Sources 当前仍合格/Scope 一致、当前客户确认资格按正式政策满足，并核对真正逻辑主题身份锁仍绑定 Review/Round/Version；只在通过后 Owner 迁移自己的正式状态。历史 ELIGIBLE/ACTIVE 观测不是当前证明。必要客户确认人已失去资格时不能默默批准，应拒绝正式化并由 PM 按业务规则撤回/重审。

RETURNED/WITHDRAWN 只消费对应结果并释放锁，不建立 current approved version，不清除已有正式旧版。撤回保留已决定与未处理 Assignment，不制造 DECIDED。业务主题锁同时禁止内容编辑、子对象变更与替换 Draft；不得仅凭 Review 表 lock 就称业务已锁定。实际 Owner 消费必须保护幂等与固定版本，不能把当前新草稿误设为批准版本。

## 锁序与并发验收

沿用当前 Auth 共享预锁→Project 当前授权事实→Review 根→Owner 逻辑身份/固定版本→Round 与 owned 子行，按实际 Owner 评审全部交叉路径；不宣称协议描述就消灭死锁。40P01 只能整 UOW rollback 后限次重试，其他异常不自动重试。最终决定与 PM 撤回同一根锁序列化，只有一个终态成功，失败不得丢失历史或多写 Audit/receipt。Owner 其他编辑/换 Draft/来源资格变更的并发需要真实环境证明。

## 历史原因缺口及下一任务

AF-02 要求撤回 reason，而 0034 无该字段，按 CR-RVW-002 登记独立 nullable 事件字段迁移，保留未知历史 NULL。原因不放运行日志或 Audit reason_code。先完成该迁移与读回，再实现可信事务 owned 决定/撤回/Audit/Owner 消费，继而接真实受权幂等入口；不能把内部合同测试当生产 ORM/命令通过。

## 验收矩阵

内部合同：精确单步、固定历史/Actor/轮次绑定、UTC/计数、首 RETURN 非终态、全体终态与撤回保留、不可变/失败关闭。后续隔离数据库：根锁并发、全部八表一致、原因读回/不可变、审计/收据/消费故障全回滚。真实业务验收：实际客户/Owner 资格、同事务正式化、Sources 当前重验、编辑及替代 Draft 阻止、释放后可控新版本，旧版保留。HTTP/三平台/UAT/Gate 仍独立待验。
