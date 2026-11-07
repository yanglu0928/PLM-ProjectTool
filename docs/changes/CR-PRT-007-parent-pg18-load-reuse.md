# CR-PRT-007：复用父包 PG18 生命周期的并发负载验收

状态：PRECHECK_RECORDED；实施前记录  
日期：2026-11-07  
适用分支：`feature/p51-a33-launcher-checksum-recovery`

## 来源与证据

- PRT-01-A11-A05-P04-P25 的独立 verifier 已因 Hosted Windows 数据目录拒绝而停止；不得重试同一独立 `initdb` 路径。此前结果见 `docs/changes/CR-PRT-006-hosted-load-observability.md` 与 `docs/progress/gate-3-a03-current-evidence-reconciliation.md`。
- 同一 Hosted Workflow 的 `smoke-parent-postgresql` 已成功启动正式打包的 PostgreSQL 18.6/pgvector 0.8.6 临时服务，并在同一服务上执行真实数据库迁移验收。该生命周期由 `tools/smoke_windows_parent_package_pg_cloud.py` 控制。
- PRT 负载业务验收由 `validation/prt-01-a11-a05-p03-approved-prototype/verify.py` 与 `validation/req-01-a12-a05-workflow-pg/verify.py` 承担，当前共同假设固定端口与自行拥有的 PG 生命周期。

## 冲突与选择

原路径要求 PRT verifier 自行执行 `initdb`，与当前 Hosted runner 的客观数据目录限制冲突。备选路径：

A. 再次变更 TEMP、目录权限或绕过数据目录检查后重复独立 `initdb`：与已记录停止结论冲突，且同类 PRT/SUR 失败已多次出现。  
B. 在新的独立 WBS 中，让 PRT 只在父包 PG18 服务运行期间创建并使用其专属临时数据库；负载结束后只删除该专属数据库，不拥有、停止或清理父 PG 集群。

选择 B。该调整只改变测试 harness 的 PostgreSQL 生命周期所有权，不改变业务请求、20 并发负载、P95 算法、500 ms Gate、HTTP/Edge 行为、产品代码或正式信任策略。

## 编码前检查

当前 Phase：Phase 2 Platform Core；Gate 3 尚未通过。  
当前 WBS：GATE-3-A03 证据重排已完成并仍为 GATE_3_BLOCKED；本 Change Request 后续实施 WBS：PRT-01-A11-A05-P04-P26。  
输入基线：锁定架构/数据模型/API Contract V1；CR-PRT-006 与 Gate 3 当前证据；父包 PG18 smoke 与 PRT P03/P04 verifier 当前实现。  
前置任务：父包 PG18/P40 有限 Hosted lifecycle 成功；独立 PRT initdb 路径已按 CR-PRT-006 关闭。  
涉及模块：仅 validation/workflow harness 与其 Hosted Workflow 接线；不修改产品运行模块。  
涉及实体：每轮唯一命名、仅供该轮使用的合成 PostgreSQL database、合成 Prototype/Requirement/Project 记录与临时文件对象。  
涉及 API：仅测试期间的内部 FastAPI/TestClient 和 loopback HTTP 测量；不新增、不改变产品 API contract。  
涉及权限：仅 Hosted runner 内的临时数据库拥有者；不使用正式 License 私钥、客户账户或生产凭据。  
验收标准：
1. Hosted Windows 2025 D:\ runner 上复用已成功启动的父包 PG18 服务，PRT 路径不启动 `initdb`、不创建第二个 PG 服务、不触碰父 smoke 的既有数据库。
2. 使用单独临时数据库完成既有业务负载断言和至少两种并发 Prototype GET 模式的受限 P95 指标采集；指标不得被描述为达到 500 ms Gate，除非实际数值全部满足基线。
3. 负载结束关闭临时应用/客户端、释放连接并删除自身数据库；父包 PG18 smoke 仍正常完成关闭与清理。
4. 保留 bounded resource summary；不上传原始日志、业务正文、连接串或临时数据库数据。
5. 运行本任务相关定向测试与同一 Workflow 的 Hosted 验证；记录每个结果及仍失败的独立工作流 job。
风险：固定端口/数据库角色/数据库生命周期接口需要从 PRT 入口安全参数化；若父 smoke 无法提供隔离且可清理的 database，则拒绝继续、不回退至失败的独立 initdb 路径。  
方案差异：从 PRT 独立拥有 PG cluster 改为仅拥有专属 database；固定性能阈值与已有业务 fixture/断言均不变。  
回滚：撤销新 verifier 入口、workflow 调用和参数化变更；恢复由 CR-PRT-006 记录的关闭状态。无需数据库迁移或产品数据回滚。  
验证计划：先做无副作用的父 smoke 接线检查；定向语法/单测；最后在 GitHub Hosted Windows 2025 执行整轮 PRT 与父 smoke，依据 bounded summary 判定。Secret 扫描后才同步代码提交。  
已知限制：该替代运行只证明 Hosted Windows Server 2025 合成环境范围，不证明用户 Windows 11、Debian 13、客户工作负载、正式 Pilot、500 ms 性能 Gate 或 Release 通过。

## 实施授权

此项属于用户 2026-09-24 起持续自主开发授权下，已记录的最小可回滚验收 harness 调整。记录同步至 GitHub 后可按 PRT-01-A11-A05-P04-P26 实施，无需重复等待普通任务批准。所有通过结论必须限定于实际证据。

## 实施记录（2026-11-07）

- PRT verifier 增加受控 loopback 父 PostgreSQL 复用模式；Requirement 回调的数据库和应用连接参数继承当前 Hosted smoke 的本轮端口/角色。
- PRT 与父烟测共享临时 PG 服务，但业务负载仍在 Requirement verifier 创建的唯一数据库中；复用模式跳过 initdb 与 pg_ctl 停止/清理，仅清理本任务拥有的文件目录，数据库由 Requirement verifier 的 finally 删除。
- GitHub Actions 将 PRT load 移入父包 PG18/P40 同 runner smoke job，并安装 backend 测试依赖。首次 Hosted 验收待本次代码提交后进行；以上为实现内容，不代表通过。

- 代码复核发现 2 处内部数据库连接仍有固定角色值；在首次 Hosted 性能任务完成前统一改为本轮父 PostgreSQL 连接参数。该修正仅限测试 Harness。
