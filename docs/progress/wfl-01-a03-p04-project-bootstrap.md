# WFL-01-A03-P04：Project 创建事务接入 Workflow

- Phase 2；前置内部初始化 P03/Project 创建与幂等实现已存在。输入冻结 Project/Workflow 模型、API-02、CR-WFL-001/002。编码前限定 Project Application 公共 Port/Windows 组合与关联测试，无跨模块表访问。
- Changed/Files：ProjectCreateService 新增 Workflow 初始化 Port，已授权新 Project 创建后、Project Audit 与收据完成前调用同事务初始化；Windows 显式平台组合始终装配真实 Workflow 服务。公开 Project DTO/路径/权限不变，无 Migration/API/依赖变化。
- 兼容：新 Port 保留可选默认以兼容旧的隔离 Project-only 内部测试/调用方；生产组合明确提供，用户请求无关闭开关。不能据此宣称所有旧内部调用或已有 Project 均有 Workflow；后续受权初始化补齐。
- Tests：Windows 11/Python 3.13 后端 625 项无失败，2 项既有符号链接环境跳过。扩展 `validation/prj-01-a04-project-create/verify.py`，隔离 PostgreSQL 18.6 真实 Session/Admin/CSRF、合成 License 拒绝、经理资格、顺序/并发幂等、可选与 Windows 显式 HTTP PASS；每个成功 Project 恰一 NOT_STARTED Workflow、六 Stage/十二 PENDING Item、一次初始化 Audit。
- 回滚证据：Project Audit 失败与初始化完成后注入失败均撤销 Project/部门/成员/Workflow/Audit/收据，原 Key 可重试成功；拒绝非管理员/CSRF/License 不创建实例。新单元测试检查同事务、真实 actor 传递、重放只调一次及初始化异常不提交。
- 测试修复：旧组合脚本未注入后来新增的文档三类 cursor 测试密钥，平台正确失败关闭；仅补充合成 fixture，未修改/弱化生产信任源行为。脚本不证明真实发行 License/密钥来源。
- Build：开发 wheel PASS，SHA-256 `b3dc545a3e43c09510ead5c2f6295db45548b726e0b4825a4f203f3e37ce0c40`。升级无需新迁移，数据库须既有 0030；既有 Project 不自动推定进度。
- Result：Windows 显式组合新项目事务接线范围 PASS；不是 Workflow 启动/推进、真实客户 Review、生产安装、Gate 3 或可用程序包验收。Server 2025 未运行，Debian 13 暂不验证。
- 清理：脚本删除自建临时库、服务停止；未修改生产/客户资料。
- Next：WFL-01-A03-P05 既有项目受权初始化前置与内部命令，明确项目负责人权限及不自动启动；Workflow GET/历史/Gate/写 API 仍需后续验收。
