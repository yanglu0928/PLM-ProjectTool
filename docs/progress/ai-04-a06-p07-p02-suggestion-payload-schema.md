# AI-04-A06-P07-P02 SuggestionPayload owned Schema0074

日期：2026-10-03；状态：`SCHEMA_PASS`；依据 CR-AI-018、DEC-753/754、Schema0074。

新增不可变 SuggestionPayload/Evidence ORM 与 Migration `20261003_0074`。数据库强制 Payload 唯一绑定 RUNNING、未发布的精确 Task/Invocation，Schema/Scope/Project同源；Payload为有界JSON object和SHA-256，事实状态固定`NOT_FORMAL_FACT`。Evidence为最多256条的有序类型引用，保存Owner/Object/Version/内容指纹，不复制正文。Invocation使用延迟复合FK指向自己的Payload，使同一短事务可先写结果再原子终态化；发布后结果与证据封存。

Windows 11/PostgreSQL 18.6 验证覆盖空库upgrade/check/downgrade/re-up、0073历史库保留NULL并升降重升、PENDING/错误Schema/Scope/重复质量标记拒绝、精确RUNNING写入、Evidence隔离、延迟FK、发布后不可变及有历史拒降；Alembic ORM drift为0。新增/更新单元后，后端全量 **2238项通过、3项既有条件跳过、2912子用例、无失败**；开发wheel SHA-256 `4ffcea6c91bf5a5ea1767ea1b11f68600d5424a04025a63872be9f7f379170f4`。

兼容/升级/回滚：仅追加表、守卫与真实FK，不改冻结API、状态枚举或生产依赖；升级前备份停写。空结果可降，有结果仅向前修复/受控恢复。未装配业务发布、未访问Provider/Secret、未外发数据；P07-P03继续实现持久RUNNING发送栅栏。
