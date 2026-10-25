# PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P01：Windows Validate运行时接线前置核查

日期：2026-10-26。状态：`PRECHECK_COMPLETE`；不改生产组合。

## 核查问题与现状

- 当前WBS：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P01`。单一问题为确定已验证Validate HTTP router接入实际Windows生产启动根的最小安全点和验收/回滚边界。
- API App与Plan版本模块已有可选router合同和独立Windows factory；默认FastAPI仍不暴露端点。实际`production_login.py`目前未导入/创建PlanVersion Create/Read/WBS/Validate router。
- 生产启动根在同一个runtime已创建当前Session/Origin/Audit/License guard；文档读取、下载与解析结果Reader也在启动初始化内创建，可复用为已批准Solution来源证明的合成/真实读取依赖。
- `create_production_platform_write_app`是唯一显式业务写平台入口；login-only与只读platform不应获得Validate route。不要复用/放宽项目授权，也不要单独“生产化”数据根或API信任源。

## 编码前计划

- 最小接线：在显式write mode中调用Windows Validate router factory，传入同一runtime、sessions、origins、License guard、Audit和已初始化的document/download/parse-result依赖；仅把返回的可选router传给create_app。
- 只增加Plan Validate路由，不同时暴露Plan Create/Read/其他路由；不修改普通登录或只读平台的路由集合。
- 若来源证明所需共享初始化晚于当前router初始化，调整为依赖就绪后的局部组合，不新建第二runtime、缓存授权或把服务对象跨进程共享。
- 验收分开：启动工厂合同先证明login-only/只读404、write router只由显式开关创建；下一WBS在Win11一次性PG18真实HTTP环境验有效Project PM/IM、非授权角色、CSRF/License/Origin、完整来源、blocked业务报告、幂等原报告重放、Audit/0189/Receipt记录数与PlanVersion状态不变。测试不触及正式安装/正式DB。
- 回滚只撤显式write app中的该router及可选参数，Schema 0189和历史报告保持不动；默认路由无变化。无新增migration/API/dependency，不改CR-PLAN-006。

## 决定

已具备复用依赖，无客观阻断。下一项：`PLAN-02-A04-P04-A04-P03-P04-S03-P03-A06-P04-P03-P02`，在实际Windows显式write启动根创建Validate router并验证login-only/只读仍不挂载；隔离PG18端到端验收单独列后续片。Gate/Pilot/Release继续保持未通过。
