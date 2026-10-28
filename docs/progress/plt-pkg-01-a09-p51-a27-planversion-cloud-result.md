# PLT-PKG-01-A09-P51-A27：A17 云端运行路径适配与首轮复验记录

- 日期：2026-10-28
- WBS：`PLT-PKG-01-A09-P51-A27`
- 状态：`IN_PROGRESS`（临时路径适配通过；完整包内 PlanVersion Edge 闭环尚未执行）
- 编码前检查：`docs/progress/plt-pkg-01-a09-p51-a27-planversion-cloud-precheck.md`
- 关联：`CR-EXEC-002/003/005`、`CR-PLAN-011/012`

## 实施与云端验证

- 将 A17 的 Edge profile 和 fixture temp root 从固定 `D:\PLMToolTemp` 改为 workflow 显式传入的非 C 盘 `RUNNER_TEMP` 后代；在 Python harness 与 Node runner 两处检查路径归属。
- 新增 Windows hosted job 对 A17 Python/Node harness 做语法检查，并断言 temp 根位于 D 盘 runner 临时目录；通过后仅清理本 job 创建的唯一临时目录。
- GitHub Actions run [40635881553](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40635881553) 于 hosted Windows Server 2025 完成，8/8 jobs 成功：后端完整测试/wheel、前端测试/typecheck/build、Python 3.13.15、PG18.6/pgvector0.8.6、embedded backend、父包组装、A17 harness 语法/非 C 盘边界检查、父包清洁解包与临时 PG smoke。
- 同源候选包含 20,118 个 payload 文件，候选 SHA-256 `eed44cfd9e56d767c9b599c850d4d4d8a783ac2ec03888d4edc4e6d39fe081c0`；父包 artifact `12794035772`，smoke evidence artifact `12793708475`。artifact 保留期 14 天。
- D 盘 runner 上清洁解包与临时 PG18.6/pgvector0.8.6 生命周期通过；结果标记 `PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED`。Manifest 仍为 `release_eligible=false`、`legal_clearance=false`。

## 未完成和限制

- 本轮新增 job 只验证 A17 harness 语法和临时目录边界；并未调用 A17 PlanVersion packaged Edge harness。因此不能宣称 A17 业务流程通过或本 WBS 完成。
- smoke 确认正式产品公钥/License trust 未打包（`FORMAL_PRODUCT_PUBLIC_KEY_NOT_PACKAGED`）、受控数据库凭据缺失（`FAIL_CLOSED_MISSING_ACCOUNT_DATABASE_CREDENTIAL`），生产 API 未启动，HTTPS 未测试；仅合成 loopback Web/API proxy 和临时 PG。
- Pilot、Gate 3、Windows 11 实机和正式 Release 继续 NOT_READY；本地没有运行程序，也未上传本机候选/资料。
- 本次新增代码未引入密钥、凭据、客户资料、运行日志或产品/API/Schema/Migration/依赖变更。远端提交前按仓库规则进行 Secret 范围复核。

## 下一步

将 A17 packaged verification harness 接入 hosted Windows runner，从同一 workflow 提供的父包候选启动实际 Edge/HTTPS/PG 合成业务旅程；继续核验所有依赖和临时写入均限于 D 盘 runner temp。只有完整闭环及清理证据通过后，才关闭 A27；再依据 Pilot 的真实信任缺项推进受控包可用性。


## A27 云端触发机制修复

- 经核查，PR #56 的 8-job checks 读取 main 现有 workflow 触发配置，因此未执行 A27 分支中新加的 A17 jobs。此结果仅证明旧 job 集合通过，不作为 A17 验收证据。
- 按 CR-EXEC-014 先记录偏差、风险、回滚及验证计划；独立 PR #58 仅将 feature/p51-embedded-runtime-cache 加入 push branches。PR run [40641140953](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/40641140953) 完成，7/7 jobs 成功；合并提交 ff5442dc7ed2c6f053c882fea08a05c698001140。
- 下一提交将作为触发器验证：必须检查新 Actions run 的 head SHA 和实际 job 清单包含 A17 candidate assembly 与 packaged PlanVersion Edge/HTTPS/PG；否则保持阻塞并继续修复触发路径。
