# CR-EXEC-014 编码前检查：A17 workflow 分支触发

- 日期：2026-10-28
- 任务：修改 GitHub Actions workflow 的 push.branches，仅添加 feature/p51-embedded-runtime-cache，以便 A27 分支上的新提交能启动其 A17 包内验收 job。
- 唯一问题：PR #56 的 checks 使用 main 当前触发规则，没有运行 A27 分支新增的 A17 jobs。
- 证据：PR run 40639658480 为 success，但 job 清单只有组件构建、父包组装和 PG smoke；不存在 A17 candidate assembly / packaged PlanVersion job。main workflow push 列表也未含 p51 分支。
- 基线/接口/Schema/依赖影响：无；只调整 CI 触发范围。
- 安全与数据：云端 runner 只使用仓库源代码、公开 pinned upstream 与合成验证数据；不读取或上传用户本机资料、客户正文、Secret 或 License 私钥。
- 验证：PR cloud checks；合并触发规则后必须由 A27 分支后续 commit 触发实际 A17 jobs，检查 run SHA、作业清单、结果和 artifacts。
- 回滚：删除新增 push filter；历史提交和证据保留。
- 结果：检查通过；变更实施后记录于 CR-EXEC-014。
