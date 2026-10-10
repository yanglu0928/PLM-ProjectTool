# CAP-01-A05-A06：Capability 五个读取 HTTP

日期：2026-10-05。结论：`CAP_01_A05_A06_READ_HTTP_PASS`。下一项：`CAP-01-A05-A07` Windows 生产组合与真实 HTTP/PG。

## 编码前检查

```text
当前Phase：Phase 2保持IN_PROGRESS；Gate 3保持BLOCKED
当前WBS：CAP-01-A05-A06
输入基线：冻结API-01/API-04、DM-05、Schema0095、DEC-840/841/844
前置任务：当前Session/User/License/Project事实读取Owner与两域签名游标已通过
涉及模块：capability api/application；platform create_app
涉及实体：CapabilityBaseline、BaselineVersion、CapabilityItem与逻辑来源引用
涉及API：CAP_BASELINE_LIST/GET、CAP_VERSION_LIST/GET、CAP_VERSION_ITEM_LIST
涉及权限：DeploymentAdmin全历史；当前项目成员仅当前APPROVED投影
验收标准：五路合同、严格query/UUID、两域游标绑定与撤权、安全DTO、默认404、wheel
风险：签名游标跨权限投影续页、子资源跨族/跨父级重放、历史Draft泄漏
```

## 实施结果

- 新增统一opt-in读取Router，接通Baseline list/get、Version list/get及Item list；`create_app` 仅新增可选注入点，默认五路均保持404。
- 读取只需可信Host和Session，不对GET要求CSRF；Owner继续重验License、当前User/Role/Project成员事实，HTTP仅输出安全投影与逻辑引用。
- 游标解码可从已验签名中恢复绑定权限投影，并通过`expected_visibility`由Owner在同一读取事务内与当前事实比较；角色变更后不沿用旧权限游标。
- 列表严格校验page size、重复/未知query、页形状、最后位置和资源归属；详情仅接受canonical UUID，Baseline返回强ETag。

## 验证与证据

- 读取Owner/游标/合同定向18项通过；覆盖默认五路404、五种安全投影、强ETag、续页权限重验、Host/Session/License、重复query、非canonical UUID和错误脱敏。
- Win11/PostgreSQL 18.6 重跟A02/A04真实数据链：管理员全历史、当前成员APPROVED投影、非成员拒绝和终态正式化均通过，迁移drift为零。
- 后端全量2594项通过、3项按既定环境条件跳过；`compileall`与`git diff --check`通过。
- 最终开发wheel内Capability/Review定向63项、解包Migration 4项通过；wheel SHA-256 `583680a9af014e66d4a7133dbfa424a8c055e1f9cf129c0bc110898dbfed0ba5`。

## 兼容、回滚与未关闭项

无Schema/Migration/依赖/配置/网络/Secret/外发变化；仅内部读取Query/Page增加权限投影绑定，两参数旧构造保持兼容。停止注入Router即可关闭新HTTP读取，数据历史不变。

Windows目标账户游标密钥与生产组合、真实HTTP/PG、前端、正式信任/性能/Gate3/发行仍未关闭；本项不宣称生产可用。
