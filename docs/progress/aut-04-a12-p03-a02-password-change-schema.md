# AUT-04-A12-P03-A02 改密首次结果Schema

## 编码前检查

Phase2/Gate3未通过；WBS A12P03A02；输入64cdf09/DM02/SC02/API02/CR-AUT007，前置bcad055 DTO/双密码proof通过。
模块Auth；实体User/前后Credential/Session/改密first；Audit只使用现有表。
API/权限：无公开路径或权限接线，仅Schema来源，不授当前认证或原子服务权利。
验收：0048/ORM一致、空及有数据0047往返旧表保持、精确前后Credential/User/Audit/time/全部Session撤销count、坏源拒绝/写后回滚/历史immutable/非空down拒绝。
风险：数据库source不证明真实密码匹配、转换前User历史状态或已实现改密事务；生产不迁移。

DEC-20260927-311：独立auth_password_change_results13字段，前后Credential三列复合FK绑定同User/version，User version+1、Credential+1；current User ENABLED/new正常Credential/自有Audit PASSWORD_CHANGED/时间链，所有Session撤销并绑定PASSWORD_CHANGED同changedAt计数。不可变历史及非空down保护，0001～0047不追写。备份维护停写升级；撤入口保历史，不自动回写旧密码或复活会话。

## 实际验证

2026-09-27 / 0.1.0.dev0 / PASSWORD_CHANGE_FIRST_SCHEMA_VERIFIED_APPLICATION_PENDING。

- 新0048 down0047及已注册ORM，13字段、4FK（其中2组三列Credential复合FK）、User新Credential/UserVersion及Audit唯一；严格UUID/不同Credential/+1版本/非零撤销/finite有序时间。INSERT核当前User ENABLED/updatedBy自己/active新正常Credential、旧新同User版本及changedBy/时间、固定PASSWORD_CHANGED self Audit前后CREDENTIAL_Vn状态和trace、全部Session无未撤销且同updatedAt/reason实际count一致。
- 实际PG18空库及有数据0047→0048→0047→0048，十二旧表保持、无backfill；ORM列/类型/nullable/PK/FK/check/unique/default一致。
- 实际含一过期未撤销Session的count2源：未撤销拒绝、错前后Credential/User/版本/trace/Audit/count/时间/未来accepted拒绝，十二旧表及first不变；自有Audit actor/action/前后状态错源拒绝。另构造全部坐标/计数正确的新must_change=true源，明确到达first INSERT后P0001拒绝，整段夹具写回滚。
- 实际first INSERT后故障回滚；后来名称/资源版本变化不改first；UPDATE/DELETE/TRUNCATE拒绝，非空down拒绝且head0048及数据完整。
- 全后端1357 tests无失败（2既有Windows权限跳过）。首轮ORM历史清单未登记新表导致一失败，补新表显式登记断言并从原历史集合分开，保原表清单严格断言，再全量通过；Migration链明确0048→0047。旧create/state/cancel/retry Schema验证head断言同步0048，四脚本实际回归通过，旧迁移文件未修改。
- Windows受限Session完整矩阵（包含状态链）及原双Scope发布实际回归通过；不声称所有历史脚本重跑。Schema凭据/角色为TEST_ONLY，无真实密码或当前授权证明。
- 开发wheel726009 bytes，SHA256 `3f2c19f256301fa68669771c6f0b89d053a9aa09a99ee0f0fa98a755d633002f`；仅构建检查，不是安装包，不上传临时wheel/库数据。

## 升级、回滚与剩余工作

正式兼容目标保持三平台；本轮仅Windows11隔离PG验证，无生产迁移/依赖/公开API/权限变化。未来升级维护停写/备份后0048；新表无历史时可down0047，有历史禁止降级丢弃。回滚撤新入口保历史，不自动恢复旧密码/会话。Schema不证明原子改密、前置User原版本真相、Scrypt密码一致性/当前Session-CSRF或收据重放；正式信任/性能/三平台/UI/完整包/Gate未通过。
下一A12P03A03：首次结果Repository与绑定前后Credential真实Scrypt source，坏源/后来凭据变化/双密码差异验证；随后原子change Service及HTTP/Windows。
