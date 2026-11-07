# OUT-01-A01-P45：真实 PlanVersion 快照重建结果

日期：2026-11-07  
状态：PASS_SCOPE_LIMITED  
变更记录：CR-EXEC-044  
Hosted run：[42307444742](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42307444742)

## 验收结果

在 GitHub Hosted Windows Server 2025 的 D 盘 owned 临时目录和同 run PostgreSQL 18 库中，A17 packaged Edge流程实际创建的 PlanVersion 固定 UUID 通过真实 `PlanVersionReadService.read_output_source` 与 `SqlAlchemyPlanVersionReadRepository` 读取。该版本来自已运行的数据库迁移与实际Owner/API流程，不是 P41 的 snapshot fixture。

- 精确 PlanVersion UUID、ProjectId、版本号1与数据库事实一致；版本状态保持 `IN_REVIEW`。
- 从持久化行重建两条 WBS，名称、TASK-002代码及 `acceptance_criteria` 字段通过断言。
- 同一版本换用随机 ProjectId 时，Owner返回 `RESOURCE_NOT_FOUND`，不暴露投影。
- A17 Hosted job成功，验证器断言失败会令job失败。P45固定marker未进入受限Artifact摘要，故本项以验证器断言与job成功作为验收证据，不声称Artifact包含独立P45 marker。

同 run 的 P25 Output HTTP/Edge failure-closed 与 A34 父包替换/显式手动恢复也成功。全run 17 jobs中16成功；唯一失败为 SUR-07-A08 packaged SurveyVersion 的 initdb 3221225781，无业务markers。CR-EXEC-039 已终止 TEMP/TMP 假设，不再重复该路线。

## 限制

本项只覆盖合成项目及 Hosted Windows Server 2025 D 盘环境；未改产品代码、API、Schema或Migration，没有客户数据、插件执行、文档生成或本机/C盘运行。状态为 IN_REVIEW，未冒充 APPROVED。该结果不证明正式Publisher trust、Output Create成功、Windows 11实机、Pilot、Gate或正式Release。

## 下一项

OUT-01-A01-P46：以本项真实 IN_REVIEW Owner projection，经生产 `FixedOutputSourceAdapter`、固定模板及 APPROVED policy、`TrustedOutputContextResolver` 与 `OutputRequestService`，验证请求失败关闭且 Output 六类持久化记录零新增。仅扩展 A17 验证Harness，test-only capability只用于使策略检查到达真实Owner来源，不执行插件。实施前登记 CR-EXEC-045。
