# CR-OUT-016：OutputRequest GET显式Windows只读组合

- 日期：2026-11-04
- 状态：P20编码前检查 PASS_WITH_LIMITATION；实施已授权
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
