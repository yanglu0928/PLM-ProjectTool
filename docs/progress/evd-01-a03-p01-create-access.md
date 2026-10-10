# EVD-01-A03-P01：候选 Evidence 创建授权边界

- 日期：2026-09-26；Phase 2 Platform Core；输入：冻结 API-02 `EVIDENCE_CREATE` 权限矩阵、现有 Session/Project 事实 Port、`DEC-20260926-137`。
- 前置核查：A01/A02 已完成定位字段合同与固定版本持久表；九型 Locator 的真实来源解析 Port 尚未装配，因此 A03 拆为 P01 授权、P02 来源/定位证明、P03 候选创建/收据/Audit，整体不标 PASS。
- Changed：新增 Evidence 内部 `EvidenceCreateAccess`，事务内重新检查当前 Session/CSRF、固定创建操作、Scope/Project 形态、GLOBAL DeploymentAdmin 与 PROJECT 的 `PROJECT_MANAGER`/`IMPLEMENTATION_MEMBER`，项目成员查询强制锁定。无生产装配或 HTTP 路由。
- Files：`apps/backend/src/plm_assistant/modules/evidence/application/create_access.py`、对应单元测试；Migration、公开 API、新依赖：无；版本 `0.1.0.dev0`。
- Tests：Windows 11/Python 3.13 角色矩阵、撤销/冒用会话、归档项目、GLOBAL 管理员、非法 Scope/目标/操作/令牌单元测试 PASS；后端 568 项无失败（2 项既有符号链接环境跳过），开发 wheel PASS。
- Result：P01 授权边界 PASS。没有真实文档定位、固定版本来源解析、候选写库或 Audit；不能用该适配器单独创建 Evidence。EVD-01-A03、EVD-01 整体、Gate 3 与可用程序包仍未通过。
- Next：P02 建立 DocumentService 所有的受权固定版本来源/定位证明 Port，并在源格式无法定位时失败关闭；P03 才能同事务创建 CANDIDATE、持久幂等及 Audit。Windows Server 2025 本项未运行，Debian 13 按用户当前指令暂不验证。
