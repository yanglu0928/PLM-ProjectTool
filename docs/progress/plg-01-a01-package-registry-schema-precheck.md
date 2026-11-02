# PLG-01-A01：PluginPackage 不可变元数据持久层编码前检查

- 日期：2026-11-02
- 状态：PRECHECK_COMPLETE / READY_TO_IMPLEMENT
- Phase/WBS：Phase 2 / PLG-01-A01
- 依赖：Gate 2 冻结 SC-01～SC-03、DM-04、API-03；DEC-OUT-001；P03 resolver boundary PASS_SCOPE_LIMITED
- 执行环境：GitHub hosted Windows Server 2025 runner；D盘runner temp；禁止用户本机/C盘运行

## 单一目标

为生产 PluginPackage 增加 PLG-01 自有不可变元数据存储（ORM + Alembic migration），建立后续签名验证、安装和 Output Operation registry 可消费的可信持久基础。本项只解决“包身份、声明操作/依赖、验证记录可持久、版本不可重写”问题，不实现签名验证、导入、安装、启停、子进程执行或 Output UI/API。

## 编码前检查

|检查|证据与结论|
|---|---|
|冻结架构/所有权|模块化单体；Plugin是唯一子进程入口，Output不得自行执行插件。读取 ADR-005、Module Boundaries、Application Contracts；Package/Installation/Execution唯一Owner为 plugin。|
|冻结模型|DM-04定义 PluginPackage 不可变 package hash、manifest snapshot、signature/signer key ref、compatibility policy、package state、verification evidence；签名密钥不进入客户运行库。|
|冻结数据库映射|SC-01定义PLG-01根表 plg_packages，owned tables plg_manifest_operations、plg_manifest_dependencies、plg_package_verifications；SC-02分类SEC-DEP、敏感字段限制；SC-03定义 plugin_id/version 唯一与后续 enabled operation 唯一查询语义。Gate2冻结提交64cdf09不改写。|
|当前实现|代码树无生产modules/plugin、无PLG migration；只有poc/poc-08-plugin-host，可作行为参考，不能作生产信任/registry。现有 Alembic head 为20261102_0221。|
|应用及接口|冻结PluginService合同包括 install(signed_package_ref)、enable/disable与invoke；本项不挂API，不制造可运行状态，所有新表写入保持Owner未安装/拒绝。|
|涉及模块/实体|仅新增 modules/plugin/infrastructure ORM 与 PLG-01 schema migration，关联作者仅使用现有平台用户FK；不得修改Output/业务模块私有表。|
|验收标准|空库完整升级、0222降级/重升；含历史数据库迁移链不丢失；包版本唯一；核心签名/Hash/manifest元数据不可变；验证结果保留追加；没有Secret/private-key/plain password列；未注册Owner写入失败关闭；ORM metadata 与Alembic schema drift一致。|
|风险|DM-04字段语义已有，SC-01 owned-table清单是候选映射；若实现发现其物理字段类型/唯一语义不足，不静默添加功能字段，先建CR；只用合成数据。|
|偏差/回滚|依赖顺序调整已记录 DEC-OUT-001。新增migration以0221为parent，不重写任何历史revision；down只允许空表回滚，存在历史记录时验证脚本必须拒绝或先安全导出/保留。|
|测试/云端验证|新增定向ORM/migration contract与GitHub hosted PostgreSQL 18空库、有历史、不可变及migration往返验收；随后后端全量/wheel及PR全链。所有临时服务与文件限GitHub runner D盘temp，job结束清理。|

## 编码文件范围

预计新增 `apps/backend/src/plm_assistant/modules/plugin/__init__.py`、`modules/plugin/infrastructure/orm.py`、Migration `20261102_0222`、对应schema tests/validation，以及更新Migration目录注册/文档。不得添加私钥或真实签名包。

## 约束

任何已签名包导入和生产验证密钥来源另设WBS；本项的合成fixture只能证明Schema约束，不能证明插件信任。不能把 PluginPackage 记录写成 VERIFIED，不能让 Output Resolver 读取未验证包的操作。
