# CR-OUT-017：OutputRequest列表HTTP接入Windows只读组合

- 日期：2026-11-04
- 状态：P21编码前检查 PASS_WITH_LIMITATION；实施已授权
- 来源：API-03 OUTPUT_REQUEST_LIST、CR-OUT-011/P14分页Owner、CR-OUT-016/P20只读组合、CR-EXEC-002 Pilot业务链
- 基线：冻结API Contract V1；不修改列表路径/查询契约、Schema或Migration

## 问题与方案

OutputRequest keyset分页Service、SQL Repository、opt-in GET adapter及独立 `OutputRequestListCursorCodec` 已存在，但未接入Windows只读组合。Codec要求专用32-byte密钥；项目中已有当前Windows账户Secret Vault只读Resolver与其他资源专属cursor来源模式。新增Output专属key ref并从当前用户/服务账户Vault解析；缺失或无效时拒绝装配，不生成/写入/重置密钥。仅在 `include_secret_read` 组合挂载列表路由。

## 风险与回滚

- cursor key缺失会导致显式read组合启动失败，必须在错误中不泄露密钥内容；默认应用不受影响。
- 不可复用Plan或Review的cursor key；Output需独立family/key。
- 回滚移除List组合和key resolver；保留P14的Service/Repository/HTTP及P20详情read。
- 不修改冻结角色、分页参数或输出投影；需覆盖三类API-03角色、project/session/page-size绑定cursor与跨项目隔离。

## 验收计划

定向Vault key resolver与路由默认/显式测试；PG18.6合成HTTP验证PM/IM/CustomerManager分页、cursor续页及隔离；完整GitHub hosted后端/前端/父包/A17/A34/A35/A50回归。仅runner D盘临时环境执行。真实vault provisioning与Win11实机不因合成验证标记通过。
