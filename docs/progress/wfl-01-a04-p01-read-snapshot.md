# WFL-01-A04-P01：Workflow 内部只读快照

- Phase 2；输入冻结 WorkflowView/API-02、DM-02 与 CR-WFL-001/002。前置四表与初始化已完成。编码前限定内部 read/投影/权限，不创建实例，不新增 API/Migration/依赖。
- Changed/Files：`workflow/application/read_workflow.py`、`infrastructure/read_repository.py`、单元测试、Project WORKFLOW_GET 读权限及事实锁、既有隔离验证脚本扩展。显式不可变字段仅 Workflow/Stage/Checklist 安全状态、固定定义版本与锁版本 ETag；不返回 ORM、私密配置、源文档或数据库定位。
- 结构：一条 SQL 同一 MVCC 快照加载全部阶段/清单，核对 V1 fingerprint、完整 key/order/required、当前阶段与状态；序列按定义顺序输出（不是依赖条目字母排序）。缺实例返回 RESOURCE_NOT_FOUND，不初始化/写 Audit/提交。固定定义版本与乐观锁版本区分。
- 权限：真实 Session/有效 License 与当前项目四角色；无项目身份 Admin 不放行；归档允许只读。WORKFLOW_GET 保持 Project/成员/部门事实锁直到读完成，避免检查后撤权。锁现复用既有 FOR UPDATE Port；性能未验，不宣称并发/P95 达标。
- Tests：Windows 11/Python 3.13 后端 636 项无失败，2 项既有符号链接环境跳过。五项新增 read 单元测试覆盖初态/ETag、畸形/不完整定义、ACTIVE/BLOCKED/COMPLETED 指针结构、同事务读与项目隔离拒绝；权限矩阵精确 16 项。
- PostgreSQL：扩展 `validation/wfl-01-a03-p05-authorized-initialize/verify.py`，隔离 PostgreSQL 18.6 四角色读、跨项目/非成员 Admin/撤销 Session/合成 License 拒绝、归档读、无实例读取不初始化、并发成员撤权 lock_timeout 拒绝 PASS。读调用前后初始化审计/实例计数不增加。
- Build：开发 wheel 包含 read 模块 PASS；SHA-256 `31a9da0b923660f1711749c0e8245c8954a0632d7438ecad3c81e7c2d249b329`。无 Migration/API/依赖变更，升级无动作。
- Result：内部只读范围 PASS；没有挂载 Workflow GET、执行 HTTP/性能/业务 Gate/UAT 或正式生产验证。视图描述存储状态，不证明客户 Review/Gate 已完成。
- Known Issues：HTTP 与 Windows 组合、Workflow/Checklist 历史、启动/推进/最终完成与真实 Gate/Owner/Review/Evidence 仍待；发行信任源/目标平台约束不变。Server 2025 未运行，Debian 13 暂不验证。
- 清理：随机隔离库删除，测试 PostgreSQL 已停止；未修改客户/生产数据。
- Next：WFL-01-A04-P02 冻结 WORKFLOW_GET 可选 HTTP、安全投影/ETag/错误与真实 PostgreSQL 契约验证。
