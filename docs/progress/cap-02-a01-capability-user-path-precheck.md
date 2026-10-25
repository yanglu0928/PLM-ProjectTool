# CAP-02-A01：全局能力基线用户路径前置核查

日期：2026-10-24；结果：`BACKEND_READY / FRONTEND_ENTRY_MISSING`。本项只核查依赖与用户路径，不把本地标准能力库文档登记为已批准 Capability。

|检查项|结论|
|---|---|
|当前 Phase / WBS|Phase 2 / `CAP-02-A01`，为 `HND-05-A02` 的当前已批准能力基线前置查清现状|
|输入基线|Gate 2 冻结 Capability `/api/v1/global/capability-baselines`、CAP-01-A05-A07 Windows 装配、CR-EXEC-002；不得把 AI 建议/资料导入自动变成正式能力事实|
|前置/模块|后端已提供五个只读、基线创建/编辑/归档、版本创建/验证/限制/送审等十二个 Operation；Windows `--platform` 只读、`--platform-write` 完整显式装配。前端当前没有 Capability 专用客户端、列表、版本或审批入口。|
|实体/API|CapabilityBaseline、BaselineVersion、CapabilityItem、GLOBAL Document/Evidence/Review；管理员历史视图与项目成员当前批准视图必须区分，游标绑定会话和可见性。|
|权限|后端 DeploymentAdmin 可读管理历史并写入；普通当前项目成员只能看到 `CURRENT_APPROVED`。基线来源限定 GLOBAL、`STANDARD_CAPABILITY`、`ACTIVE` 文档的 `AVAILABLE` 固定版本；正式批准经独立 GLOBAL Review，不允许项目负责人或 AI 自动代批。|
|验收目标|先补只读能力基线列表/详情/当前批准版本与条目发现入口及严格权限分页；再补全球标准能力文档固定来源的受控选择、基线/版本草稿与正式送审/Review UI；用两类角色和隔离 PG/Edge 证实批准前不可供 Handover、批准后可见。|
|风险|本地“标准能力库”文件存在不等于产品数据库中已批准的全局 Capability；仅有 Handover 创建分析正向包内证明，当前一次性空库无能力基线。前端若只添加 UUID 输入或隐藏草稿，会误导用户认为已完成审批。正式服务账户密钥/发行公钥仍独立未满足。|

静态交叉核查 `capability/api/read.py`、`commands.py`、`submit_review.py`、来源验证与读服务、Windows 生产装配记录及前端路由/模块。没有 Schema/API/权限改动，没有外发客户数据；未运行新功能测试或宣称 Capability 正式确认。Result：`CAP-02-A01_PRECHECK_PASS`。Next：`CAP-02-A02` 先实现受权 Capability 列表/详情的可见性正确读路径，再连续推进全局来源与 Review 创建链。
