# EVD-01-A04-P03-A07：Windows 显式平台资格写组合

日期：2026-10-01；Phase 2 Platform Core；结论：`WINDOWS11_SYNTHETIC_COMPOSITION_PASS / FORMAL_TARGET_OPEN`。

输入为冻结 EVIDENCE_SET_ELIGIBILITY、A05真实PG资格链、A06并发单赢家、现有 Windows `--platform-write` 显式组合。编码前核查：DocumentReadService、Session/CSRF写 Port、项目授权、License Guard、Audit、收据和Evidence ORM均已可注入；仅修改组合根及原隔离组合验收，不改 Schema/API 合同。资格路由只在显式写组合注入；登录专用与只读组合不开放 POST。

全新临时 PostgreSQL 18.6/pgvector + 合成 Windows 配置/License/密钥上，实际组合创建候选后资格 POST 200，同键重放200、ETag v1、单条资格 Audit；外部用户404、角色降为 CustomerMember 后404。登录专用路由404，只读组合的同路径 POST405（与现有 GET 路径共享匹配，但方法仍关闭）。原创建/列表/Viewer、内容篡改/撤销/License 行为回归通过。完整隔离组合脚本退出0；后端全量1797项/3跳过、wheel构建通过。临时PG停止并清理。

当前仅合成目标账户/License/文件/密钥；正式 Windows 11 目标账户可信时间、正式公钥/License、独立 Evidence 游标密钥供给及恢复、HTTPS/发行与UAT未验。Windows Server 2025/Debian 13不据Win11推定通过。Gate3不变。回滚为不启用 `--platform-write` 或撤资格路由注入，保留既有审计/资格历史。
