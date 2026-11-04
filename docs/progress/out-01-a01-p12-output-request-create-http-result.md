# OUT-01-A01-P12：OutputRequest Create HTTP 可选边界结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-009
- 代码提交：f9301077bb3d293e4683370d6109d858774ed13f
- Hosted run：[41780566043](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41780566043)

## 实现与边界

- 新增单一可注入的 POST /api/v1/projects/{project_id}/output-requests router，默认不挂载。
- 严格限制五个冻结字段：output type、template version、source version refs、output policy ref、plugin operation；拒绝多余字段和重复source。
- 复用 Session/CSRF/origin检查及内部 OutputRequestService。Owner继续负责 Project角色、License、固定来源/能力、事务幂等、Job和Audit。响应只含 output_request_id、job_id、state 与 trace_id。
- 对外错误映射为稳定安全码；不返回内部异常。没有新增 Migration、API Contract修改、默认产品组合、插件调用或文件发布。

## 验收

Hosted run 41780566043 的 14/14 jobs 成功：后端 3,979 项测试和 wheel、前端测试/typecheck/build、PG18.6/pgvector0.8.6生命周期、20,185文件非发行父包、A17、A34、A35、A50。HTTP tests 使用合成session/service覆盖202最小投影、Session/CSRF、额外字段/重复source拒绝、安全错误映射。父包SHA-256：71974fb894df0fc8ddab2e5d48257b0082c556d2f3b6a0f2dd1189075dbd12d4。hosted临时目录使用D盘；用户本机未运行程序和测试。

## 限制

路由尚未挂入正式应用；生产publisher registry为空，P11能力查询仍使Output生成失败关闭。本项未启动产品API、未调用插件、未生成客户文件。Pilot、Gate 3和正式Release仍NOT_READY。
