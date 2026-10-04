# AI-04-A06-P05-P02 Invocation PlanRef 数据库守卫

日期：2026-10-03；状态：`SCHEMA_PASS`；依据 CR-AI-015/016、DEC-741/742、Schema0073。

新增 Migration `20261003_0073`，以独立 INSERT 触发器补齐0072后的数据库最终守卫。新 Invocation 必须绑定非空 PlanRef，并与 Task、授权快照和 Content Plan 的静态身份、策略、Prompt/Schema、Context、Provider/Model/revision及请求payload证明完全一致。旧NULL历史不回填且不能在升级后继续新增；0073不修改0064既有状态机，也不把历史守卫冒充当前授权或Lease检查。

Windows 11/PostgreSQL 18.6 验证覆盖：空库upgrade/check/downgrade/re-up；含NULL旧Invocation的0072数据库升级、保留、拒绝新NULL、降级/重升；新库拒绝NULL、跨Plan与payload漂移，接受精确PENDING Invocation；存在非空PlanRef历史时拒绝降级。Alembic ORM drift为0。新增单元2项，后端全量 **2211项通过、3项既有条件跳过、无失败**；wheel SHA-256 `d2301d828172e76fc2eec67d5c4ec5b8a7c79c1fe96f4c245f4754eb97f2ca46`。

兼容/升级/回滚：无ORM字段、公开API、依赖、外发或生产装配变化；升级只安装触发器。空历史可降，产生新Invocation后仅向前修复。下一项 `AI-04-A06-P05-P03` 实现无正文Invocation Begin合同与短事务Repository，原子插入下一Attempt并更新Task当前指针；当前仍无业务Invocation writer或Provider调用。
