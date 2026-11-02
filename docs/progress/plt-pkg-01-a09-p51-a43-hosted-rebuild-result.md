# PLT-PKG-01-A09-P51-A43：Windows 受控试用包云端重建结果

- 日期：2026-11-02
- 状态：PASS_LIMITED（当前源码的托管 Windows 重建与组合验收）
- 编码前检查：plt-pkg-01-a09-p51-a43-hosted-rebuild-precheck.md
- GitHub Actions：https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370951575
- PR #61 分支 head：4cbf2c140a1515029e5823bba1bd6935a5c33399；PR 合并构建提交：9713443955f7698a687c620ab3647971f8700847。

## 云端验收结果

- 12/12 workflow jobs 成功：后端全量测试与 wheel、前端测试/typecheck/production build、固定来源 Python 3.13.15、PostgreSQL 18.6/pgvector 0.8.6、embedded backend、父包组装与核验均通过。
- 当前 PR 源码父包候选 ZIP SHA-256：63ed5c8d209f09cb9fa22aeacf9245aeb8cfebf0cff8397beea26e591dc05a7a；20,118 个 payload 文件。GitHub artifact 容器摘要为 1a7ec0c2a26a8eb2252817598d5a83cb1c9e94d3b4e57968dcc808843168255b，artifact ID 13109214144，372,785,728 bytes，保留至 2026-11-16。容器摘要与内部父包 ZIP 摘要对应不同层级。
- 同一 run 在 hosted D 盘临时区完成清洁暂存、临时 PostgreSQL/pgvector 初始化/查询/停止；A17 PlanVersion Edge/HTTPS/PostgreSQL 合成流完成 29 次 API 调用，业务状态为 IN_REVIEW，未产生人工/客户决定；A34 旧/新候选隔离替换、失败候选隔离和明确手动恢复演练通过。
- 父包临时生命周期结果为 PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED；A17/A34 均为 PASS_LIMITED，不是正式信任或发行验收。

## 阻断与结论

- 父包入口按设计 fail-closed：缺少账户数据库凭据时拒绝启动；正式公钥、License trust、数据库凭据引用、服务账户/ACL、TLS 等外部前置仍不齐。服务、产品 API、真实数据库和监听器均未启动；未安装产品。
- 候选保持 release_eligible=false、legal_clearance=false、formal_startup_ready=false；结果不构成 Windows 11 新验收、Pilot 就绪、Gate 3 通过或正式 Release。
- 产物为 Actions 临时 artifact，可在 run 页面下载，保留期截至 2026-11-16；未创建正式 Release。
- A43 没有本机运行。Hosted Windows Server 2025 结果不能推定 Windows 11 兼容。

下一任务：继续 Windows Pilot 关键路径，优先实现并云端验证正式启动前置信息的安全接线/诊断，使外部信任输入缺失时给出可操作、无秘密回显的阻断结果；在完成 A44 编码前检查和先行差异记录后再编码。Pilot、Gate、正式 Release 维持 NOT_READY。