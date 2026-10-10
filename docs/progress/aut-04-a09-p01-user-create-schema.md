# AUT-04-A09-P01：首次User创建结果

2026-09-27 / INTERNAL_SCHEMA_PASS，非User创建功能整体PASS。

## 编码前检查

- 当前Phase：Phase2 Platform Core；当前WBS：AUT-04-A09-P01。
- 输入基线：冻结64cdf09、CR-AUT-005、原0006凭据历史、0045实际head；前置A08设计已记录。
- 涉及模块：Auth拥有结果，Audit仅来源FK/数据库不变量；应用间仍调用公开Audit Port。
- 涉及实体：User、初始PasswordCredential1、USER_CREATED Audit、Auth UserCreateResult。
- 涉及API：无新HTTP；涉及权限：无新增权限，Schema不是Admin/Session/CSRF/License或密码证明。
- 验收标准：严格不可变DTO；ORM及0046一致；空/有数据up-down-re-up保留旧表；来源/形状/唯一/时间拒绝、实际回滚；历史非空down拒绝。
- 风险：不得重放当前变化后的User，不得存密码/hash/额外快速摘要，不回填旧用户。实际密码核验/授权原子编排尚属P02/P03。

## Schema细化（实施前记录）

表`auth_user_create_results`以user_id为PK，credential_id/user_id/credential_version复合FK绑定原Credential1，actor_id FK原User，audit_event_id FK且唯一，trace_id；仅保存首次UserReadView八字段及accepted_at。无密码、hash、canonical、请求正文或额外密码摘要。

INSERT触发器必须锁定目标User并核实ENABLED/NONE、version1/lock1、active Credential1/原creator/updater；显示名与创建/更新时间精确等于当前首次源；Credential changed_by=原actor、非强制换密、有限日期且created<=changed<=updated；Audit精确USER_CREATED/USER/DEPLOYMENT/SUCCESS/AUT-01/目标User/原actor/trace，空project/version/reason/before/originalactor/hint，after ENABLED，updated<=audit<=accepted。接受时间DB statement_timestamp；不猜应用时钟，不把源证明当授权。

UPDATE/DELETE/TRUNCATE全部拒绝。后续合法User变更不重验或改写历史。FK保留源，不伪造旧用户首次结果。非空down锁表后拒绝；空down仅移除此新增表和其函数。升级停写备份；撤未装配入口回滚保留全部历史；无生产迁移。

## 执行证据

- 新`UserCreateResult`严格首次安全View/非零UUID/非自创建/有序aware时间、不可变及被篡改nested View再核；五新unit。全后端1282项无失败，2既有Windows符号链接权限场景跳过。
- `validation/aut-04-a09-p01-user-create-schema/verify.py`真实PG18隔离库：空与旧有数据0045→0046→0045→0046，十旧表全行不变、新表空不回填；ORM columns/nullability/FK/check/unique parity。
- 使用实际Auth Repository创建/初始凭据激活和Audit Port，严格错误id/actor/trace/快照/state/role/version/time/Audit action/当前来源拒绝且十一表无额外写；真实插入后异常回滚，重复及UPDATE/DELETE/TRUNCATE拒绝；目标后来停用/改名原首次记录不变；历史down拒绝并保0046及十一表原行。凭据`TEST_ONLY`仅Schemafixture，未证明Scrypt、当前Session-CSRF、幂等命令或授权。
- 新validator附原双Scope实际文件发布回归通过；两旧Schema validator仅把当前head断言推进0046（保旧迁移），实际Job retry generation/取消首次结果往返与历史保护及其原发布回归exit0。
- `aut-04-a07-windows-user-list`两实际Windows组合/真实Session权限分页与旧发布回归exit0。显式正向信任合成，不是正式供给。
- 开发wheel构建694351 bytes，SHA256 `7f2ceb45e4811fe88e3ae1c04fc4a93df427cec62d1a1ddc548a86f0d35cdb14`；本地忽略产物，不是可用离线安装包。

Changed/Files：Auth DTO/ORM、0046、unit/真实validator、head回归断言、本文/DEC294/STATUS/CHANGELOG/CR-AUT-005。Migration：0046仅隔离库验；API：无新router/路径/权限/依赖。Result：本Schema子项PASS。Known Issues：真实原始Scrypt核验、原子receipt/Admin-CSRF/创建HTTP/Windows写及提交确认异常/性能/正式信任/Gate/最终包未完成。Next：AUT-04-A09-P02初始不可变凭据只读证明及ReplayVerifier。
