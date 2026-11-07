# CR-OUT-016：OutputRequest GET显式Windows只读组合

- 日期：2026-11-04
- 状态：P20 PASS_SCOPE_LIMITED；P21为下一项
- 来源：API-03 OUTPUT_REQUEST_GET、CR-OUT-010/P13 Read Owner、CR-EXEC-002 Windows内部Pilot业务链
- 基线：冻结API Contract V1；不改变路由/DTO、架构、Schema或Migration

## 问题与决定

冻结详情GET已有只读Owner、project-scoped SQL投影与opt-in HTTP adapter，但未接入生产Windows显式read组合。实现仅增加组合factory并在 `include_secret_read` 分支挂载，复用Session/Project member read/License/Output Repository。默认和登录App保持未挂载。

## 风险与回滚

- 投影超出范围会泄漏Context正文或存储位置；继续复用固定View adapter与SQL安全投影。
- 授权必须来自当前有效Session及Project read Owner；跨项目/不存在统一404。
- 回滚移除Read factory、显式组合参数与测试；保留P13 Owner/HTTP与P19 Create。
- 不涉及DB迁移或API合同变化。

## 验收计划

定向默认/显式路由与项目隔离测试；hosted PG18.6合成HTTP验收；全量后端/前端/父包及A17/A34/A35/A50回归。全部只在GitHub runner D盘临时环境运行。


## P20实施与验收结果

- 仅在 `include_secret_read` Windows组合挂载既有OutputRequest详情GET；默认/登录/不含read trust的应用不暴露。
- Run [41835015557](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41835015557) 13/13 jobs成功：后端4,021 tests/wheel、frontend、PG18/pgvector、父包、A17/A34/A35/A50通过。
- PG18.6验证Project成员成功读取；非成员和跨项目统一404；Context marker与文档路径未出响应；Output/Job/Outbox/Audit/receipt行数不变；默认路由未挂载。
- 非发行父包20,202文件，SHA-256 `8d24b79a138340dd02053baddb97a4364ddaf725254a20d9af4cf236bb999d70`。结果为PASS_SCOPE_LIMITED；Session/License/数据均合成，不代表真实信任、Win11实机或Gate/Pilot/Release。
