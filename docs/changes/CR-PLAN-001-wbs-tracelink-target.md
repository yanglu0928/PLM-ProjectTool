# CR-PLAN-001：统一 TraceLink 增加固定 WBS Item 目标类型

日期：2026-10-19。状态：`APPROVED_BY_CONTINUOUS_AUTHORIZATION`；实施/验收尚未完成。来源：`PLAN-02-A04-P04-A04` 编码前核查。

## 原基线及冲突证据

Gate 2 冻结架构要求合同→调研→需求→原型→方案→WBS 的正式追溯，项目 Skill 明确“正式 WBS Task 必须具有可反向查询的 TraceLink”。冻结数据模型中 WbsItem 是 PlanVersion 内实体；当前 TraceLink `TraceVersionRef`、`trc_links` CHECK 和 API 资源类型仅识别 PlanVersion 的 `PLN-02`、参考计划 `PLN-03`。`PLN-02` 的 object_id/版本语义无法同时表示 Plan 根/版本及具体 WBS Item；仅把 WBS 外键存于Plan内部表也不是统一 TraceLink。原冻结提交 `64cdf09` 不修改。

## 方案比较与选择

- A（选择）：在统一 TraceLink 的类型白名单中追加 `PLN-02-WBS`，其 object_id=`wbs_item_id`、version_id=`plan_version_id`、scope=`PROJECT`；Plan Owner 按 WBS/PlanVersion/Project 同一快照证明目标存在、权限和资格。原 `PLN-02` 语义保留。使用既有 `TraceLink` 表、查询、审计与授权入口，不创建Plan平行Trace表。
- B（拒绝）：仍用 `PLN-02` 只链接PlanVersion；无法反向定位单个WBS Task，不满足正式追溯。
- C（拒绝）：在Plan内部另存关系并称为Trace；与统一Trace双写且缺受权反向查询。

## 差异、影响与实施顺序

新增类型是对冻结Trace资源白名单/物理CHECK的可追溯加法修订，不删除或改写原类型、`/api/v1` 路径、成功/错误Envelope、权限或License机制。先追加受控类型与迁移，再添加Plan目标证明/公开资源解析Port，后续PlanVersion Owner在创建与验证/送审时建立或核对统一TraceLink。未接入真实Owner前，类型白名单只表示可表示性，缺Port时仍失败关闭，不能把WBS身份或AI建议当正式业务事实。

## 迁移、回滚与验证

迁移只替换Trace源/目标类型CHECK以允许新类型，不改已有行；升级前备份，Windows 11/PG18.6空库及已有Trace数据升级、旧类型回归、非法类型拒绝、降级/重升与drift验证。新增类型尚无历史行时可降；一旦存在该类型历史，降级必须拒绝并向前修复或按受控备份恢复。类型Owner还须独立测跨项目、错版本、撤权、License及反向查询；完整业务链在Gate/UAT另验。

剩余风险：WBS Item 是版本内实体，跨PlanVersion的任务延续不由同一object_id推断；需独立Trace边或比较合同明确。正式Approved Solution、Evidence资格、Trace Owner、Plan业务Owner/HTTP/UI/Output及Pilot/发行仍待。此CR不预先判定Gate通过。
