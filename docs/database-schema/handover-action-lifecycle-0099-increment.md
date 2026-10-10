# Handover Action Lifecycle Schema 0099 增量

日期：2026-10-05。迁移：`20261005_0098 -> 20261005_0099`。范围：HND-03生命周期投影、固定响应/Evidence及append-only事件完整性；本项不开放HTTP或业务状态Owner。

## 状态与投影

- 唯一前向链为`OPEN -> IN_PROGRESS -> SUBMITTED -> VERIFIED -> CLOSED`；ProjectManager后续Owner可从OPEN/IN_PROGRESS/SUBMITTED/VERIFIED进入`CANCELLED`。
- 每次状态转换Root `lock_version + 1`，`updated_by/updated_at`必须与唯一下一序号事件Actor/time一致；事件连续且`from_state`必须等于前一事件`to_state`。
- SUBMITTED首次固定`submitted_at`；VERIFIED首次固定`verified_by/verified_at`；CLOSED首次固定`closed_at/resolution_trace_ref`。字段不得清空或改写，CANCELLED保留已有投影且不冒充closed_at。
- CLOSED/CANCELLED不可复活；元数据PATCH仍失败关闭，后续以独立Owner/Schema增量开放。

## Owned refs 与当前事实

- SUBMIT前只允许在IN_PROGRESS插入固定response DocumentVersion和SUBMISSION Evidence；提交后至少各一项。
- VERIFY前只允许在SUBMITTED插入VERIFICATION Evidence；验证后至少一项。
- VERIFIED可追加RESOLUTION Evidence；所有response/evidence/event均insert-only，不可修改、删除或truncate。
- 延迟完整性重验所有response为同项目AVAILABLE DocumentVersion、所有Evidence为同项目ELIGIBLE记录；CLOSED还必须引用同项目ACTIVE TraceLink。具体解决来源/目标事实仍由后续Close Owner验证。
- AnalysisItem只在Action初建/v0时要求`DRAFT/CANDIDATE`或`APPROVED/CONFIRMED`；后续状态转换只要求固定同项目来源仍存在，避免Review进入IN_REVIEW后使合法Action无法推进。

## 升级、回滚与验证

0099只替换0098守卫与延迟触发器，不新增表/列/索引/依赖。所有Action仍为OPEN/v0、零owned refs且只有seq0事件时可降回0098；存在任何生命周期历史则拒降并向前修复。离线downgrade固定拒绝。

Windows 11/PostgreSQL 18.6已验证空历史降升、drift、完整前向链、缺响应回滚、固定Document/Evidence、同项目ACTIVE Trace关闭、OPEN取消、历史不可变、终态不可复活和有历史拒降。合成Survey Trace仅证明Schema机制，不代表真实业务解决。
