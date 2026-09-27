# AUT-04-A11-P02 User状态首次结果Schema

## 编码前检查

- Phase/WBS：Phase2 / AUT-04-A11-P02，Gate3未通过。
- 基线/前置：64cdf09/DM02/SC02/API02；CR-AUT006与P01 DTO/Domain43fd926已记录并unit通过；旧0046保留。
- 模块/实体：Auth-owned独立UserStateResult，FK只引用原User/Audit；Session仅校验源。
- API/权限：不挂启停HTTP，不是当前Admin授权或完整状态命令。
- 验收：ORM/0047一致；空及有数据up/down/up旧表保留无回填；绑定目标/current字段/有效Credential/Audit和时间；DISABLE无未撤销Session且撤销数来自同updatedAt+USER_DISABLED实际源；历史不可改/删/截断，非空down拒绝。
- 风险：快照source一致性不证明原状态确实转换、调用者授权、最后Admin或同Key原子性。实际命令要P03再验证。

DEC-20260927-303：新增独立auth_user_state_results；private result/actor/audit/trace/operation/version/count与safe8View，数据库有限时间/版本+1/状态和exact源检查。revoked_count核对同一User updatedAt的USER_DISABLED事件组，不把count当授权；ENABLE计数0且不复活旧Session。回滚撤入口保history；仅空表允许down0046，生产不执行迁移。

## 结果与验收范围

- Result：SCHEMA_INTERNAL_PASS（Windows11/隔离PG18），完整状态命令INCOMPLETE，Gate3不关闭。
- Changed/Files：新增0047和UserStateResultRow注册原UserORM，更新迁移head/metadata inventory、真实状态Schema验证器和旧三个迁移验证的current-head断言；0001～0046文件不改写。
- Migration/Review：单新增表16列、3 FK、2 unique、shape约束与精确源/不可变trigger；源先锁target，只返回safe字段，非秘密private来源；有限ordered时间且acceptedAt不得晚于本次DB statement时间。down先ACCESS EXCLUSIVE并确认表空；非空拒绝避免丢失历史。没有生产迁移。
- Tests：1328后端无失败（2既有符号链接权限跳过）；真空/有数据0046→0047→0046→0047、十一旧表原样和无回填；新ORM列/类型/nullability/PK/FK/check/unique/default一致。actual User/Credential/Audit源，未知ID/actor/trace/action/state/role/credential/version/name/time/futureAccepted/count拒绝零额外写；存在未撤销Session拒绝，实际2个Session（含超时未撤销）按同updatedAt撤销后count2才能接纳。真实snapshot insert后故障全回滚；再ENABLE记录0并无旧Session复活，后来改名/状态保原快照；UPDATE/DELETE/TRUNCATE P0001，非空down P0001且head0047/原表保留。
- Regression：旧User create Schema、Job cancel snapshot、Job retry schema三个actual up/down/来源/immutable验证通过；Windows名称PATCH actualFactory真旧/新登录及历史/权限/启动隔离/缺正式信任拒绝通过；原双Scope空/260行实际文件发布、取消/许可/身份/故障/锁竞争回归通过。未重跑全部历史脚本。
- Build：开发wheel711157字节，SHA256 `99c230978a0c64e7cfdc0cf0caf0a2ab348e4d792a857798e07ea11faa0e5b91`；非安装包，不提交wheel。
- API/Known Issues：无新增HTTP、权限、依赖或Key；Schema夹具Credential为TEST_ONLY，不是当前认证/完整状态转换/原子receipt/最后Admin/自停用/Session竞争证明。正向License合成，正式材料/三平台/性能/UI/完整包待。
- Next：AUT-04-A11-P03原子内部启停命令，部署锁/当前Admin-CSRF/版本/全Session/审计/immutable first/receipt与最终许可授权；真实并发与写后/提交确认故障矩阵通过后再HTTP/Windows。
