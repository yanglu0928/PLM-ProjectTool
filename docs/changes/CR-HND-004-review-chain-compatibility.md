# CR-HND-004：Handover Review 真实链兼容修正

日期：2026-10-05。状态：依V1.1持续授权已实施并验证。关联 `HND-01-A04-A02-P01/P02`、Schema0101、CR-HND-001/002；不改写Gate 2原冻结提交`64cdf09`。

## 触发与差异

P02使用全新Windows 11/PostgreSQL 18.6临时库运行真实Review创建/开轮/终态链时发现两项原方案不兼容：

1. Schema0101共享INSERT触发器在表名分支条件内直接引用`NEW.item_state`，PostgreSQL对其他Handover子表记录解析该字段并报错。P01的既有DRAFT/Review状态夹具未覆盖正常Version子表完整插入，因此原P01 wheel `149a4c...58c046`只能保留为历史构建证据，不再作为候选包。
2. 既有Version仓储要求Root正式指针必须为空才能创建Draft，导致首版批准后无法创建下一版，与冻结多版本、`supersedes_version_ref`及Schema0101的`APPROVED -> SUPERSEDED`模型冲突。

## 选择与实施

- 触发器改为先按`TG_TABLE_NAME='hnd_analysis_items'`进入独立分支，再读取`item_state`；不放宽任何初始状态约束。
- Version创建去除“正式指针必须为空”的旧限制；仍要求ACTIVE Root、来源摘要一致、强ETag、无IN_REVIEW，并保持现有正式指针不变。只有新Version未来被真实Review批准时，终态Owner才原子替换指针并SUPERSEDE旧正式版。
- 新增Handover真实PROJECT Review Subject Owner与仓储，固定`HANDOVER_ALL_V1`；创建/送审/批准重验真实Subject、当前来源、Evidence、Capability、AI provenance、评审人及Action覆盖。退回/撤回不确认Item、不替换正式指针。

## 风险、迁移与回滚

无新表列、公开API、依赖、网络或数据外发。触发器修正影响尚未发布的Schema0101定义；已安装旧0101的开发库需重新应用修正版迁移或向前修复，不得假定同revision内容自动更新。Version创建放宽只允许在已有正式版本且无在审版本时创建受控Draft，不扩大角色或跳过强锁。

回滚可停止装配新Subject Owner；已形成的Review、批准指针和Item确认历史必须保留。代码回滚不得恢复会阻断正常子表插入的触发器，也不得恢复“批准后永远不能升版”的旧条件；如需撤销行为，只能新增向前Change Request/Migration。

## 验证

修正后P01 Schema验证在全新库重跑通过；P02真实链完成创建、开轮、批准、批准后新建下一版、再次创建/开轮及撤回，最终V1为APPROVED/Item CONFIRMED且仍是正式指针，V2为RETURNED/Item CANDIDATE。定向36项、后端2667项通过/3项条件跳过，wheel解包导入通过，SHA-256 `3954fa5175350eb61ec36ea410d150f0e7ae56e4ccb1a5b014060922bc8e08eb`。
