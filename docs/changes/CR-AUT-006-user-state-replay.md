# CR-AUT-006 User启用/停用可靠命令

日期：2026-09-27；版本0.1.0.dev0；状态INTERNAL_ATOMIC_VERIFIED_HTTP_PENDING（CR整体发行验收仍待）。
依据：用户2026-09-24/27持续授权；原冻结64cdf09及0001～0046保留。

## 来源与证据

- 冻结API02 AUTH_USER_ENABLE/DISABLE要求当前DeploymentAdmin、Session/License/CSRF、幂等Key、强If-Match、Audit；disable撤销全部Session。
- DM02：DISABLED不能新建Session，旧Session全撤销，凭据与身份历史保留。
- 现有UserCommandService仅创建，无状态服务；通用receipt只有ref，0046首次快照专用于创建。不能复用当前GET或USER_CREATED记录冒充原状态请求响应。
- 自停用后原当前Admin-CSRF Adapter必然拒绝；简单跳过最终授权会放宽安全，简单全面禁止自停用则缩窄功能。冻结未明确最后Admin规则，以下新增保护按持续授权记录，非原文已确认事实。

## 比较及选择

1. 只实现无幂等内部UPDATE：不满足冻结I/M/A，拒绝。
2. receipt引用当前User：目标之后重新启用/改名将改写重放语义，拒绝。
3. 独立不可变Auth状态首次结果 + 原receipt + 同事务User/Session/Audit，选择。完整支持普通用户和Admin目标，支持有其他启用Admin时自行停用，不以缩窄范围替代安全设计。

## 设计增量

- 新增Auth状态首次结果：独立UUID、User/actor/Audit/trace来源、operation、expected_version、first safe8字段、revoked_session_count及acceptedAt；ENABLE只DISABLED→ENABLED，DISABLE只ENABLED→DISABLED。版本必须先比较，实际转换+1；新Key对已经目标状态不产生假成功。相同Key重放仅返不可变首结果，即使当前目标后来变化；每次仍核当前调用者和License。
- ENABLE必须具有现有非零有效Credential，不能复活旧已撤销Session。DISABLE撤销目标所有尚未撤销Session（含已超时），原因USER_DISABLED，Session lock_version+1；已撤销记录不重写。名称/角色/凭据/创建历史不改。
- 最后一个启用DeploymentAdmin不能被停用。自行停用只有其他启用Admin存在才允许；首次请求成功后自有Session也撤销，后续未授权重放401/404，不为恢复幂等绕开停用。
- Application在状态变更之前取得部署级事务锁，统一状态命令锁序，重新查询当前Admin及目标，最后Admin计数必须来自锁定事务，不接受客户端count。其他Auth入口并发、真实锁竞争/死锁须验收，不把纯Domain规则当原子证明。
- 非自停用末尾原Auth重核；自停用必须专门验证已锁定原Actor/Session、仅本命令造成目标停用/版本与全部Session撤销，Credential/角色不变，原认证时间仍有效，再核License；不得无条件绕过最终授权。具体数据库实现与真实攻击矩阵留后续任务，不开放未验证入口。
- Snapshot数据库来源检查绑定当前目标、精确Audit动作/前后状态/actor/trace和ordered timestamps、DISABLED无未撤销Session；历史UPDATE/DELETE/TRUNCATE拒绝。不可变快照是首次响应证据，不替代当前权限或整个状态变更的证明。

## 迁移、回滚与验证计划

已新增0047和对应ORM，原0001～0046不追写；未迁移生产。空库及有数据0046→0047→0046→0047、十一旧表/ORM一致、源拒绝与不可变、非空降级拒绝已真实PG验证。DISABLE count绑定同User updatedAt/USER_DISABLED源组，actual2Session含expired来源通过，future accepted拒绝。升级人工备份/维护停写；有状态历史不得降级丢弃，回滚撤入口保数据库，生产故障按已验证备份人工恢复。证据见P02progress/Schema增量；不是完整命令授权与原子性证明。

后续内部命令验收：enable/disable、凭据0、普通/非Admin/CSRF/License、target历史/全Session、stale/Key冲突、同Key并发、启停后首响应、Admin互相停用/自行/最后Admin、实际Audit/receipt/result/Session写后故障全回滚、提交确认前后故障、新Session与停用竞争；再HTTP/Windows write、安全Cookie及真实新旧登录。20并发和三平台另验，不伪报。

## 当前范围与剩余风险

已完成前置、纯Domain/严格首次结果DTO、0047/ORM及真实Schema来源/历史验证；P03新增持久内部原子命令、实际当前Admin-CSRF、全Session撤销、首响应与原收据、自停用末核和最后Admin保护。1336 tests无失败（2既有跳过），真实PG/Scrypt同Key竞争、写后/提交故障与恢复、互停/自停用/55P03超时/登录竞争及原发布回归通过，见P03progress。HTTP/Windows尚未接线，Gate3与正式发行不关闭。明确TEST_ONLY角色夹具及合成License不证明生产认证供给。无新Key、依赖、角色、SSO或授权机制替换。License独立UOW前后检查仍不是业务License事务锁；所有其他Auth锁序与性能尚待验证。
