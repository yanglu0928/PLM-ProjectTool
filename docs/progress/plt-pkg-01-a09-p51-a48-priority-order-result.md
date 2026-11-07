# PLT-PKG-01-A09-P51-A48：就绪阻断项优先顺序

- 日期：2026-11-02
- 状态：PASS_LIMITED
- 执行环境：GitHub hosted Windows Server 2025，D盘 runner temp；用户本机未运行。
- 最终验收：[workflow run 41386839114](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41386839114)，12/12 jobs成功。
- 源代码head：`4158bde7dd805cbd78a50fe8275c941694fdd692`；云端合并提交：`b1c5a44e59fae6435bf9f41b046d7a11f79a4691`。

## 变更

readiness JSON新增固定有序 `recommended_actions`，把仍缺的正式产品公钥/License、数据库凭据范围、Windows服务身份/ACL、TLS证书/域名四组事项排序。每项只含静态 blocker code、字段名、责任角色和下一步动作；中文报告按同顺序显示。它是操作建议，不关闭门禁或授予启动/发行。

## 云端验收

- 最终 run 12/12 jobs成功；后端3,849项、前端构建、固定来源重建、PG18.6/pgvector 0.8.6、父包清洁解压、A17/A34组合通过。
- 父包 smoke 覆盖正常不完整登记四组顺序、完整登记但启动blockers仍存在、无效输入不回显，以及临时副本零blocker+完整登记边界。零blocker分支动作列表为空，但JSON/文本仍显示独立核验；四个授权/准入布尔值保持false。原父包manifest/hash清单不变。
- 父ZIP SHA-256：`8e642dc1c4393fdae80935622349b094122b18509816fc8ce4a9d7805aa48948`，20,122 files。artifact ID `13115832553`，外层artifact SHA-256 `c713f4d9f1e504933f06479e1500b96776cf421a4b85d404d49a62c562eb3495`，372,794,278 bytes。
- readiness smoke证据 artifact `13116610048`；summary明确 `complete_zero_blockers_still_not_authorized=true`。
- A17：29次合成API、PlanVersion IN_REVIEW、WBS/requirement/validation=(2,2,1)、customer decisions=0；artifact `13115579973`，PASS_LIMITED。
- A34：旧/新包20,119/20,122 files，失败隔离和显式手动恢复通过；artifact `13115664399`。

## 偏差与兼容性

首轮run [41385387249](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41385387249) 的核心顺序场景全绿，但没有端到端覆盖零blocker完整登记；差异先写入A48前置记录，再补临时manifest分支并重新运行完整工作流。临时manifest只在D盘runner temp使用，真实候选manifest和摘要保持不变。

新增JSON字段及可读文本，既有API/DB/schema/License与退出码不变，无迁移。只验证hosted Windows Server 2025，不推定Windows 11；产品未安装或启动。正式公钥/License、DB凭据身份、服务ACL、TLS及法务放行仍缺，Pilot/Gate 3/正式Release继续NOT_READY。
