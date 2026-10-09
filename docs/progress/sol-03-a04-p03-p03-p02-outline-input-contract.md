# SOL-03-A04-P03-P03-P02：OutlineVersion DRAFT 创建输入合同

日期：2026-10-09。结果：`SOL_03_A04_P03_P03_P02_OUTLINE_INPUT_CONTRACT_PASS`；仅纯输入规范化，Owner/数据库写/HTTP 仍关闭。

## 编码前检查

- 当前 Phase/WBS：Phase 2 Platform Core / SOL-03-A04-P03-P03-P02。
- 输入基线/前置：Gate2 DM-05/API-04、CR-SOL-002/017、0155 封闭首响、Section/Requirement/Reference 现时证明、DEC-20261009-1141。
- 单一问题：在 Owner 写入前建立固定有序 Section、批准 Requirement、合格 Reference 和缺失/冲突声明的确定性、有限界、不可歧义输入合同，防止伪空 DRAFT 或重复固定来源。
- 模块/实体/API/权限：Solution Application 纯数据类与验证函数；不读 DB/外部服务，不新增公开 API、Schema/Migration、角色或依赖。授权与现时性仍由后续 Owner 同事务执行。
- 验收：顺序保留、规范请求指纹、合法无参考方案/显式缺失草案；空章节、全空来源、重复根/版本、错误 Scope、非法/过大/深层 JSON 失败关闭；定向及后端全量。
- 风险：请求指纹只证明请求字节等价，不证明来源当下仍有效；实际版本内容指纹必须加入当前 Section/Requirement/Reference 证明，不允许拿客户端摘要代替。

## 实施与验证

`OutlineVersionDraftInput` 固定项目/目录、有序 SectionId、Requirement 根/版本、Reference Scope/根/版本和两组声明。验证要求 1～100 Section；Requirement/Reference 各不超过 500，二者都空时至少一条结构化缺失声明；每类拒绝重复根/版本。声明为最多 100 项 JSON 对象数组，各规范 UTF-8 编码不超过 64 KiB，拒绝非字符串键、NaN、过深对象；通过规范编码生成幂等请求指纹，返回声明字节副本以隔离调用者后续修改。无硬编码未冻结的声明业务字段。

定向 5 项/13 子例、后端全量 3442 通过/3 跳过/5256 子例，保留既有 2 条告警。无数据库/API/升级变化，未接线合同可撤回。下一项 `SOL-03-A04-P03-P03-P03` 建立 Owner 在同事务内的当前 Outline/Section/Requirement/Reference 证明与内容指纹组合，再实施 INSERT-only Guard/持久首响/审计。Gate3 仍 BLOCKED。

TraceLink：Gate2 DM-05/API-04 → CR-SOL-002/017 → DEC-1141 → 本输入合同 → OutlineVersion Owner。
