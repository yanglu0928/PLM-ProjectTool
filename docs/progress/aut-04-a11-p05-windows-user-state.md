# AUT-04-A11-P05 Windows User状态装配

## 编码前检查

当前Phase：Phase2，Gate3未通过。当前WBS：AUT-04-A11-P05。
输入基线：冻结64cdf09/API02、CR-AUT006；前置P04 f19e61f可选状态HTTP真实PG验证通过。
涉及模块/实体：Auth User/Session，Windows composition root。
涉及API：冻结启停，仅显式platform-write安装；readonly/login/default关闭。
涉及权限：复用已验证当前Admin-CSRF/License与状态事务链，不新加Key/角色/fallback。
验收标准：实际Factory运行完整P04矩阵、真实HTTP创建/登录/停用旧401/启用新登录/历史首响应；readonly/default无写；新增依赖失败和缺正式材料拒绝半启动。
风险：正向信任仍合成，不能当生产密钥或Server2025/性能/安装包证据。

DEC-20260927-306：仅include_secret_write作用域构造UserStateService及真实access/repo/results/receipt，传可选router给create_app。无Migration/依赖/API变化；撤接线保历史。

## 实施和验证

2026-09-27 / 0.1.0.dev0 / WINDOWS_INTERNAL_COMPOSITION_VERIFIED。

- 真实Windows write Factory安装已验服务/access/repo/first/receipt，readonly不构造新增依赖，普通/login无入口；缺正式信任锚仍拒绝启动，无测试回退。
- 全后端1344 tests无失败（2既有Windows权限跳过），实际隔离PG18 Factory重跑P04完整矩阵；另实际HTTP创建→Scrypt密码登录→NONE停用拒绝八表不变→Admin停用→旧Session GET401/停用账户登录401→Admin启用→新登录200同UserID→旧Session仍401→原Key历史first重放八表不变。
- 五个新增依赖逐一注入构造故障均实际到达并静态拒绝，创建的数据库runtime.dispose实际各调用一次；readonly均未构造这些依赖，POST405无写；default/login404。首轮只读断言误设404，因已有User详情通配GET产生405，核查后改为405，生产代码和权限不变。
- 正式信任未模拟时，两platform Factory实际拒绝且八表不变。旧Windows名称PATCH完整矩阵与原双Scope文件发布回归通过；未声称所有历史验证脚本重跑。
- 开发wheel719469 bytes，SHA256 `ff457b18a26841d05b613860b42b3d50fc5f2e641b758c2f28f20de8cdb07db8`，仅构建检查，不是安装包、不上传wheel/临时数据。

兼容0047，无Migration/依赖/生产升级/角色变化。回滚撤write接线保状态历史。测试License/游标密钥为显式临时合成来源，角色提升为TEST_ONLY，不证明正式账户信任供给。Server2025/Debian/20并发/浏览器UI/完整管理面/安装包/Gate3未验。下一AUT-04-A12：管理员重置密码前置，核对冻结临时密码/强制改密/全Session及不可变首次收据语义，不直接挂未验接口。
