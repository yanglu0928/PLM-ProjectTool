# CR-EXEC-033：SUR-07-A08 复用经过校验的 staging 准备

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据与根因

Hosted run [42263308077](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42263308077) 的 A08 失败摘要为 FileNotFoundError、WinError 2、固定阶段 PACKAGED_SMOKE_START；有界调用帧显示 verify.py:291 → smoke_current_app_packaged_https.py:160 → 同文件:71 → _local.py:670 → 净化的 _frozen_ntpath_:709。

源码证据：smoke_current_app_packaged_https.py:160 调用 _inputs；该函数在第71行对 stage 执行 resolve(strict=True)，所以必须已存在。A08验收器只传入stage路径，未从同run候选包创建目录。既有 tools/run_a17_packaged_cloud_validation.py 的 extract_verified 对候选SHA、路径、元数据、manifest、逐文件校验后创建该 staging 目录。结论为A08测试Harness接线遗漏；没有产品API/业务缺陷证据。

## 单点修正

仅在 SUR-07-A08 verify.py 中复用既有 extract_verified；调用前验证目标为D盘 temp 的直属、ASCII、全新目录，stage名使用 plm-current-app-stage-a08-<run id> 以符合 _inputs 前缀；extract_verified 校验并解包同run A17非发行候选，然后运行原smoke。Workflow 仅变更stage目录名。pristine/target继续满足既有 plm-install-rehearsal-* 校验。

不更改产品代码、API、Schema、数据库、License、权限或任何验收标记/断言。

## 风险、回滚与验证

风险是重复读取/校验完整候选会增加Hosted D盘时间；此举保留完整性边界且避免未验证解包。回滚限于删除新增 staging 调用并恢复workflow stage name，其他A08/A17流程不动。以完整 GitHub Hosted Windows Server 2025 D盘 run 验证 stage 创建、PG18/Edge/HTTPS流程、三个原有A08/A12标记和 owned-root 清理；原始日志不上传，数据仅合成，无客户外发/外部AI/插件执行。


## Hosted 结果与后续根目录对齐（2026-11-07）

run 42266017538 证明CR-EXEC-033的候选 staging创建和包清单校验已完成。失败随后发生在 packaged platform-write / migration smoke 开始处：smoke_packaged_pg18_migration._migration_temp_root拒绝A08的PLM_P51_TEMP_ROOT。该helper的行109固定要求 selected.parent.parent == RUNNER_TEMP、selected.parent.name以 plm-p51-a27- 开始、selected.name为PLMToolTemp；A08当前run根名不满足，PG18进程尚未启动。按CR-EXEC-034先记录；仅重命名A08精确owned runRoot为兼容前缀，再跑完整Hosted流程。
