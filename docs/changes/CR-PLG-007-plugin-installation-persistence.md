# CR-PLG-007：实现冻结PLG-02安装事实的持久化基础

- 日期：2026-11-04
- 状态：已登记；按用户持续自主执行授权进入实施，客观验收未完成前不得关闭
- 原因：OUT-01-A01-P10确认当前缺少PluginInstallation、enabled operation及runtime validation持久化Owner；冻结模型/SC-01已定义PLG-02根及owned tables。
- 范围：只实现冻结PLG-02的PostgreSQL ORM/Migration和Schema验证；不改Gate 2基线内容、不新增Root、API、依赖、插件执行器或正式信任来源。

## 决定

依冻结Data Model、SC-01映射和SC-02 M-DEP profile，新增Migration 20261104_0225：

- plg_installations：安装身份、精确Package复合引用、plugin normalized id、安装状态、当前validated runtime snapshot、安装/启用责任主体及UTC时间、M-DEP创建/更新与lock_version字段。
- plg_enabled_operations：安装所选启用操作，复合引用精确Installation和该Package的Manifest operation；操作行唯一，并以(plugin_id_normalized, operation_id)唯一索引阻止同一插件操作同时由多个Installation启用。
- plg_runtime_validations：保留安装运行环境检查快照、兼容结果、检查主体及UTC时间；只追加，不允许UPDATE/DELETE。
- 新表初始保持Owner写入口关闭；分别拒绝TRUNCATE。后续PLG-02业务Owner WBS再按明确生命周期命令开放最小写入，不由PLG-01包验证Worker写入。
- Installation精确指向Package及normalized plugin id；状态用冻结值INSTALLED/ENABLED/DISABLED/INCOMPATIBLE/RETIRED。本次迁移不创建安装、启用、信任或客户事实。

## 偏差、风险、兼容与回滚

这是既有冻结Root/table mapping的物理Migration实现，不新增或重定义Schema/API/Data Model基线。列按M-DEP通用字段语义展开。不涉及外部API或用户数据迁移，无新增运行依赖。

父子复合FK、部分唯一索引和保护触发器的风险由GitHub hosted PostgreSQL 18验收覆盖：空库升级、既有PLG-01行保留、约束反例、空表降级重升、有记录降级拒绝。降级仅当三个PLG-02表全空时允许；存在记录即拒绝以保留事实及版本链。失败时不开放Owner写入；先记录CR偏差，再修复代码/夹具，不删除历史。

## 验收

实现后在GitHub hosted runner的D盘临时空间执行ORM契约、后端全量/wheel、PG18迁移与父子约束/Owner写关闭/TRUNCATE/有数据降级反例、Windows父包及A17/A34全流程。禁止本机/C盘运行项目代码或测试。

## 授权边界

按用户已持续授权自主实施。此CR不授权真实发布者Key/信任、客户数据访问或外发、插件正式安装/启用、插件代码执行、付款、强推或不可恢复生产变更；验收结论仅按实际hosted run记录。
