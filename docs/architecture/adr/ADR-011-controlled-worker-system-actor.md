# ADR-011：受控 Worker 系统身份来源

Date：2026-09-26；Status：ACCEPTED_UNDER_CONTINUOUS_AUTHORIZATION / WINDOWS11_INTERNAL_SOURCE_PASS。

## Context / Decision

ADR007要求SystemActor，实际代码尚无来源。按实施前CR-AUT-004，Platform提供只读assert_current公共Port；Windows以当前运行账户Vault专用`worker-system-actor-v1`材料经固定域SHA256派生稳定UUID，启动pin完整摘要，每次使用再读取且一致才返回。复用既有本地provision/export/restore加密备份，不自动创建、替换或接受客户端身份。详见CR方案比较/威胁边界/风险与恢复。

UUID只是审计来源，不授予Session、角色、License或项目权限。不新建系统User/密码。Owner使用前必须保留原User/Scope/trace/purpose并核当前权限、Job/Lease和文件/result事实；此来源不能让SYSTEM跨项目通配。信任Windows运行账户及Vault，不承诺防同账户恶意代码或管理员，不用材料签名、不复用其他密钥。

## Consequences / Verification

Windows11临时Vault失密拒绝、错误口令、加密恢复原UUID和换材料拒绝实测通过，4新增/934后端无失败（2既有跳过）、开发wheel成功。未装配实际Worker/HTTP；正式账户与离线口令保管、异账户/Server2025灾备、Debian来源与原子发布/Gate仍待。不以临时引用外推生产。

## Migration / Rollback / Trace

无Schema/API/依赖变化；停Worker后由实际保管者恢复原材料，真正身份轮换另做可追溯迁移，旧Audit不改。撤未装配入口不会删除Vault/历史。保留原冻结64cdf09与ADR007，依据CR-AUT-004、DEC-20260926-214和`docs/progress/aut-04-a01-controlled-system-actor.md`反向追溯。
