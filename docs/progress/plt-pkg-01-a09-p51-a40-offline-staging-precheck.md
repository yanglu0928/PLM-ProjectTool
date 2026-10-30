# PLT-PKG-01-A09-P51-A40：Windows 11 D盘离线候选安全暂存入口（编码前检查）

- 日期：2026-10-30
- 状态：编码前检查完成；CR-PKG-012实施前安全细化已先记录并提交。

当前Phase：Phase 2 Platform Core；Gate 3 未通过。
当前WBS：PLT-PKG-01-A09-P51-A40。
输入基线：冻结安全启动边界；CR-PKG-012及2026-10-30实施前安全细化；A35 Windows 11真实父包；A38只读就绪诊断。
前置任务：A39 PASS_LIMITED；父包无安装入口，且签名/License/服务身份/TLS/DB门禁未齐。
涉及模块：独立开发者/运维辅助工具 `tools/stage_windows_parent_candidate_offline.py`；重用现有 `stage_windows_parent_candidate_cloud.py` 的完整 ZIP/manifest/逐payload散列安全校验。
涉及实体：包外verification-summary.json、候选ZIP、非 C盘 `RUNNER_TEMP` 内的新隔离暂存目录及固定字段暂存回执。
涉及API：无。
涉及权限：只读候选ZIP/summary；写入仅限显式指定、已存在的非 C `RUNNER_TEMP` 直系新目录；不触碰真实安装根/用户文件，不联网、不读密钥/credential，不启动服务/DB/API，不执行Migration，不重启。
验收标准：CLI必须提供完整SHA绑定的非发行verification summary；重用候选身份/安全路径/重复成员/链接/扩展名/清单/逐文件hash校验；目标目录必须是新的RUNNER_TEMP直系子项且非C盘；完成后写入明确 `installation_performed=false`、`services_started=false` 的回执；错误仅输出固定代码/异常类型且清理只限owner staging。Windows 11 D盘对A35真实候选执行一次完整离线暂存并用A38报告器确认仍阻断；定向测试覆盖拒绝路径、错误SHA和回执非授权字段。
风险：误把隔离暂存当作安装；summary不可信；临时目录清理越界；包内launcher误启动。回执保持非发行/未安装，summary须匹配整个ZIP SHA，暂存命令不调用launcher。
回滚：删除新CLI及其测试/文档；复原暂存器默认hosted receipt标签；无需还原数据库/API/服务或安装目录。
