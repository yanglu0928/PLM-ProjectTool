# CR-PLG-014：PluginExecution 持久化基础

- 日期：2026-11-05
- 阶段/WBS：Phase 2 Platform Core / PLG-03-A01
- 状态：实现及PG18独立验收待完成
- 基线：Gate 2 冻结 PluginExecution R-PRJ Aggregate、PLG-03；SC-01 映射 `plg_executions`、`plg_execution_result_files`、`plg_execution_state_events`。
- 来源：P32证明后续OutputArtifact固定FK依赖PluginExecution物理Root；OutputArtifact必须等待本项。

## 编码前核查

当前冻结模型已定义单次插件执行身份、PROJECT Scope、installation/operation、固定OutputContext/fingerprint、Job/attempt/idempotency、PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED、result manifest/fingerprint、安全错误码、时间及trace。当前分支已有Package/Installation/EnabledOperation/RuntimeValidation数据及Jobs/Output/Document基础，但没有PluginExecution ORM/表/Migration与Owner。

## 决策及范围

本WBS只建立冻结PLG-03持久化结构：Execution Root、append-only result-file references与state events，ORM/Alembic/DB约束/索引；约束ProjectId与OutputRequest/Context、PluginInstallation、不可变PluginPackage/Manifest operation及Job关系；不把历史外键绑定到停用时会删除的可变EnabledOperation记录。后续Execution Admission Owner须在当时验证EnabledOperation状态。没有执行器、文件移动/创建、生产写Owner、API、默认Worker挂载或Plugin subprocess。执行表初始写入保持DB trigger closed；迁移验证夹具仅用隔离合成行。

Result field只保存安全引用/指纹和受控错误码，不存储stdout、完整客户Context、绝对工作路径、traceback、Secret或文件正文。合法生成内容进入Artifact的流程仍必须以后独立核验FileObject/DocumentVersion/PluginExecution/Hash全部一致。

## 风险与验收

- 状态与事件表必须保持同一Project与Execution身份；结果文件必须引用已有FileObject并拒绝跨Project记录。
- empty DB升级、含既有合成数据升级、空库downgrade/reupgrade；有Execution历史时downgrade必须拒绝并保留行。
- 验证状态白名单、时间约束、Attempt/Job幂等唯一语义、复合FK、result-file引用、append-only、TRUNCATE保护和Owner write closed。
- 后端全量测试/wheel、hosted PostgreSQL 18.6真实Migration/verifier及父包PG smoke；测试通过前不得称Artifact链可用。
- 仅GitHub hosted Windows runner D盘；无客户数据、Plugin运行或外部API调用。P25仍独立blocked。

## 外键设计复核（编码前）

EnabledOperation是当前启用投影，Disable流程会删除该行并保留不可变History。若Execution外键引用EnabledOperation，停用插件将被历史Execution外键阻断，违反既有PLG-02-A06生命周期。故Execution持久化引用稳定的Installation复合身份及不可变Package/Manifest Operation；“创建时仍启用”由后续Execution Admission Owner校验并在事务内固定Execution事实。该设计调整在PLG-03编码开始前记录，不改变冻结模型。

## 首轮 hosted 验收偏差（2026-11-05，修复前登记）

- run [41968008173](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41968008173) 的后端全量测试运行 4,052 项，恰有2处旧基线断言未跟随本次Schema扩展：Migration head仍期待 `20261104_0230`；metadata历史表豁免清单未包括新增的3张PLG-03表。没有PLG-03业务断言、Migration执行或PG smoke结果，故不能据此判定DDL通过/失败。
- 修复计划：将Migration head断言更新为 `20261105_0231`，并把3张冻结PLG-03新增表加入metadata schema inventory；不改业务代码、DDL、迁移约束或Scope；随后重跑托管全量。

## 第二轮 hosted PG验收偏差（2026-11-05，修复前登记）

- run [41968716925](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41968716925) 的后端全量、前端、wheel及sidecar通过；父包PG smoke在既有 `OUT-01-A01-P01` 迁移Verifier的空库升至head检查处停止，Verifier仍硬编码期待 `20261104_0230`。因此PLG-03独立schema verifier尚未运行，不能据此判断本次Migration的PG行为。P25仍是独立initdb阻断。
- 修复计划：仅将旧P01 migration verifier的当前head预期更新为 `20261105_0231`，保留原有的up/down/upgrade业务断言，然后重新运行完整Hosted链。不得删减P01验收项或把新head误报为P01的业务变化。

## 第三轮 hosted PG smoke偏差（2026-11-05，修复前登记）

- run [41970235945](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41970235945) 的后端全量测试、前端/build、wheel、父包组装、A35、A17 candidate、P24与A50已通过。父包PG smoke在旧P01验证器的合成数据清理断言处停止：`plg_executions`已按PLG-03外键引用`plg_installations`，但既有TRUNCATE测试未把新Execution根及两个子表纳入同一语句，PostgreSQL因此先返回 `FeatureNotSupported`，未进入PLG-03专项迁移验收。该错误是测试夹具清理范围遗漏，不能据此判定Migration通过或失败；P25仍独立阻塞。
- 修复计划：将PLG-03三张新表列入schema presence inventory，并将Execution根、result-file、state-event与安装历史相关表一起纳入批量TRUNCATE负例；保持原断言、不使用CASCADE、不删除验收。

## 第四轮 hosted PG smoke偏差（2026-11-05，修复前登记）

- run [41971678555](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41971678555) 后端全量、前端/build、父包组装、A35、A17 candidate、P24与A50通过。父包PG smoke已越过P01迁移验证，随后在 `validation/plg-01-a01-package-schema/verify.py` 的隔离staging库current-head断言失败：PLG-03新增迁移将schema head推进至 `20261105_0231`，PLG-01 verifier仍将自己的旧head常量锁在 `20261104_0230`。PLG-01专项与PLG-03专项验证均未运行完成；本失败不代表新Migration通过或失败。P25仍为独立状态。
- 修复计划：仅将PLG-01 verifier的current-head常量推进至 `20261105_0231`，保留PLG-01已有历史revision/表/约束断言；无业务代码、迁移DDL或Scope变化。然后重跑托管全链。

## 验收环境

仅 GitHub hosted Windows runner D盘临时目录运行；不在用户本机/C盘执行代码。无客户数据、外发、插件执行或生产写入。


## Hosted PG verifier cross-check before next run（2026-11-05，修复前登记）

- 在修复PLG-01 current-head检查前，对父包PG smoke显式调用的其余迁移verifier进行源码盘点，发现 `validation/plg-02-a06-operation-disable/verify.py` 的“有历史数据时downgrade拒绝且head不变”断言也将当前head硬编码为 `20261104_0230`。该断言属于PLG-03持久化增加后的兼容验收，未更新会在PLG-01通过后继续中断PG smoke。
- 修复计划：仅更新上述当前head值到 `20261105_0231`；保留downgrade拒绝、历史保留及其它PLG-02既有断言。此项由源码盘点先行发现，尚无对应运行失败证据；与CR既有真实偏差记录区分。


## 第五轮 hosted PG smoke偏差（2026-11-05，修复前登记）

- run [41973267273](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41973267273) 后端全量、前端/build、依赖/父包组装与A35/A17 candidate/P24/A50通过。父包PG smoke依次通过P01迁移链及PLG-01 staging head，到PLG-01空库旧触发器数量断言时失败：验证器用全局 `tgname LIKE 'trg_plg_%'` 统计，固定期望21；新增PLG-03三表提供6个独立保护触发器后结果为27，尚未执行PLG-01后续及PLG-03专项断言。该失败是历史验证器范围耦合，不是触发器错误或Migration通过证据。
- 修复计划：在PLG-01验证器中明确排除PLG-03三张表，只统计PLG-01/02既有关系上的历史21个guard；PLG-03 6个guard继续由PLG-03专属验证器以精确名字与行为独立检查。保留PLG-01/02原21项断言，不降低阈值、不更改业务DDL；随后重新运行Hosted链。
