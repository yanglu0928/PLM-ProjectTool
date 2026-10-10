# AI-04 Schema0065：输入版本业务对象身份

日期：2026-10-02；父版本 `20261002_0064`；依据 CR-AI-010/DEC-700 与冻结三字段 `ResourceVersionRef`。

`plm.ai_task_input_refs` 新增可空 UUID `object_id`，并将索引调整为 `owner_module, object_type, object_id, version_id`。物理可空仅用于保留0063既有不可变历史；0065数据库INSERT守卫要求所有新行 `object_id` 非空且非零，原Scope/Project/QUEUED及追加后不可变规则保持。

升级不猜测历史ObjectId。读取遗留NULL的后续服务必须以 `AI_INPUT_REFERENCE_UNRESOLVED` 失败关闭，不得执行/重试或把VersionId冒充ObjectId。空库或仅遗留NULL历史可降0064；出现任何0065完整身份后拒绝物理降级，使用向前修复或受控备份恢复。
