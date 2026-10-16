# AUT-04-A11-P03 内部原子User启停

## 编码前检查

- Phase/WBS：Phase2 / AUT-04-A11-P03；Gate3未通过。
- 基线/前置：64cdf09/DM02/SC02/API02、CR-AUT006；P01规则/DTO和P02实际0047 Schema87ad5b0通过。
- 模块/实体：Auth User/Session/statefirst；Audit与Platform receipt只用原Port。
- API：冻结enable/disable内部服务，不公开HTTP，不增加角色。
- 权限：实际当前Admin Session-CSRF/License；目标状态版本与凭据；自停用必须另一个enabled Admin存在，并专门核验原锁定身份和本命令撤销源，不无条件绕过末核。
- 验收：同事务User/全Session/Audit/first/receipt；同Key首响应/不同载荷冲突、后来启停后仍首View；当前权限/License重放再核；并发/Admin互停/自停用/最后Admin/旧Session不复活；实际写后/提交确认故障回滚或原收据恢复。
- 风险：状态命令专用部署事务锁先于Admin/target，其他Auth入口仍可不同锁序，死锁/lock timeout安全回滚，非性能证明；License独立UOW前后检查非业务License锁。

DEC-20260927-304：专用transaction advisory锁(1347177793,1431524436)序列化启停/最后Admin计数；新UOW lock_timeout5s避免无界锁等待。CurrentActor immutable proof绑定User/Session/credential/原时间版本，自停用末核验证原Token/CSRF绑定、唯一预期状态变更、原凭据/角色、Session原生命周期仍有效且仅USER_DISABLED同时间+版本撤销、其他Admin与无未撤销会话。不接受客户端actor/count/proof。保存严格0047first并复用原receipt，无新Schema/Key/依赖。撤未接线服务保历史。

## 实施与实际验证

状态：INTERNAL_ATOMIC_VERIFIED_HTTP_PENDING；版本0.1.0.dev0，日期2026-09-27。

- Application、当前Actor专用proof、状态Repository及不可变first Repository已实现；同UOW写User/全部未撤销Session/Audit/first/receipt，提交前再核权限和License。ENABLE不恢复旧Session，DISABLE包括已过期但未撤销Session，不重写已撤销记录。
- 全后端1336 tests无失败，2项既有Windows权限相关跳过；8项新增unit。实际隔离PG18验证脚本：`validation/aut-04-a11-p03-user-state-atomic/verify.py`。
- 真Scrypt目标登录；同Key并发启用/停用仅一首次结果；历史状态首响应不随后来启用变化；冲突、旧版本、当前非Admin/坏CSRF/许可拒绝均无写。旧Session不复活，新登录可用；停用与建Session竞争后无未撤销目标会话。
- 七个实际写后故障、提交前故障整体回滚七表；实际提交后确认丢失返回不可用，原Key恢复已提交结果且无额外写。真实部署锁等待捕获SQLSTATE 55P03，安全失败且七表不变。
- 自停用实际专用末核通过，原生命周期到期及伪造proof拒绝；停用后旧身份不得重放，重新启用后的新认证可恢复原首结果但不撤销新Session。最后Admin/双Admin并发自停用保留一个启用Admin；互相停用竞争败方当前身份被拒绝。
- 原双Scope文件发布真实回归通过。验证过程中曾因互停夹具提前增加Admin而使“最后Admin”预期失败；将独立互停夹具移至该验收之后，不改生产逻辑、不放宽断言，保留此原因记录。
- 最新开发wheel717520 bytes，SHA256 `a7522bac887730ef8509fc452bd8c724b36dc2eaa5af03c041014289d7b0db0d`；仅构建检查，不是安装包，不上传本地wheel或测试数据。

## 兼容、回滚及限制

沿用0047，无新Migration/依赖/角色/Key，无生产迁移。撤未接线内部服务并保留状态历史；不得有历史时强行降级0047。真实测试包含明确TEST_ONLY角色提升及合成License，不能证明生产信任供给。不同Auth入口所有锁序/20并发/性能、HTTP、Windows装配、界面、三平台、正式包和Gate3均未验收。下一AUT-04-A11-P04：按冻结合同接可选状态HTTP并验证。
