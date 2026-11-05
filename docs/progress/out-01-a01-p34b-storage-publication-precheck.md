# OUT-01-A01-P34B 编码前检查：Storage与数据库发布协调

- 日期：2026-11-05
- 结论：PASS_WITH_LIMITATION，可实现隔离的内部发布协调Owner；不接API/Worker/default composition
- 基线：ADR-008、CR-OUT-030/031、P34A PASS_SCOPE_LIMITED、P33 PASS_SCOPE_LIMITED
- 环境约束：实现与验收只在GitHub hosted Windows Server 2025 D盘临时区/隔离PG18执行

## 源码与边界核查

1. LocalFileStorage已提供canonical project locator、publish_verified、verify_content、inspect_recovery、recover_verified_final及recover_linked_pair。恢复分类只对具体命名路径与sha/size作只读核验；NONE、BOTH_UNRELATED、UNSAFE不可清理/覆盖。
2. Document FilePublishService使用USER授权、USER Audit和USER幂等命令，Output Job需要SYSTEM执行身份/原请求人审计，不能伪装或直接复用该应用服务。P34B新增Output专用内部Owner及Repository。
3. P34A要求最终FileObject已AVAILABLE；它创建Generated Artifact DocumentVersion/source ref并推进Document指针。P33之后创建Artifact、完成OutputRequest/Job和Audit。依赖顺序固定为：FileObject发布事实 → P34A版本Owner → P33成功终结Owner。
4. Windows本地文件系统和PostgreSQL不能跨资源原子提交。P34B使用短数据库事务、事务外hash/提升、短数据库事务核验fence并提交AVAILABLE/Audit；再调用P34A/P33。遇到文件已提升而DB仍STAGED时仅允许final-only/linked-pair按存储原语复验和恢复；DB已AVAILABLE的重试必须复验final文件后继续；未知形态始终失败关闭且保留文件。

## 实施合同

- 首个短事务按OutputRequest→Job Claim→Execution→FileObject→Document顺序核验并冻结STAGED文件元数据，不在持锁期间读取/散列大文件。
- 事务外先inspect_recovery，再仅按STAGE_ONLY调用publish_verified、FINAL_VERIFIED调用recover_verified_final、LINKED_PAIR调用recover_linked_pair；NONE/BOTH_UNRELATED/UNSAFE均失败，不自动删除或覆盖。
- 第二个短事务重新核验相同Request/Execution/Job fencing、Document/FileObject/locator/hash/size/MIME和STAGED状态，原子将FileObject变AVAILABLE、插入FileStateEvent、写SYSTEM Audit。已AVAILABLE仅在所有绑定和final locator完全一致时作为重试事实。
- 提升后以同一claim调用P34A，再由P33终结Artifact和Job；不直接SQL绕过P34A/P33。
- 若Owner已P33成功而重复提交，验证final字节后只允许P33严格成功重放；不能重新发布或重复Audit。

## 风险与回滚

- 文件系统副作用不可由数据库回滚撤销。最终文件无法证明时保持原样/失败关闭；不盲删。不一致文件交由受限人工诊断。
- DB AVAILABLE 后执行P34A/P33失败时保留可读文件和事实，允许同Claim精确恢复。fencing失效时拒绝进一步业务提交。
- 不新增Schema/API/Migration、Worker、插件执行或默认组合。回滚仅撤回未装配Owner/验证器；不删除已提升文件。

## 验收

Hosted Windows runner D盘临时根 + 隔离PG18；真实文件系统纯合成内容。覆盖STAGE_ONLY正常提交/无覆盖/hash读回、FINAL_VERIFIED、LINKED_PAIR、安全恢复、NONE/不相关/unsafe拒绝、错误Project/Request/Execution/Document/File/fence、DB/Audit失败后final-only/AVAILABLE重试、精确重放和P33成功终结；backend全量/wheel与父包/A17/A34/A35。只有专项和全链断言通过后P34B才PASS_SCOPE_LIMITED。

## 实施记录（2026-11-05）

按本检查与CR-OUT-030/031新增隔离的Output SYSTEM发布协调Owner/Repository，并扩展父包PG18 verifier使用GitHub hosted Windows D盘临时文件系统。未接API、Worker、插件或default composition。代码已准备提交，Hosted验收尚未完成；此文档不代表P34B通过。