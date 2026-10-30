# PLT-PKG-01-A09-P51-A33：启动失败时显示安全前置诊断编码前检查

- 日期：2026-10-30
- 前置：A30已提供只读非秘密诊断脚本；A31已验证README在父包根目录调用；A32已验证该父包级脚本不进入应用运行布局。
- 当前问题：payload/start-trial.ps1 在信任前置未满足时统一输出泛化的固定文案。父包已能提供精确的BLOCKED阻断代码/说明，但用户直接启动时看不到诊断，需要额外找到并运行README中的单独命令。
- 单一目标：在启动入口发现真实候选不满足既有守门条件时，向调用者转发同一个只读诊断脚本的安全报告，然后仍以非零状态固定拒绝启动。
- 范围：仅修改父包启动入口、现有parent PG smoke中对实际打包启动入口的验证和必要README操作说明；不实现正向生产启动，不更改manifest/信任判断，不读取凭据Secret或私钥，不启动服务/Caddy/数据库，不写安装位置，不放宽启动守门。
- 设计约束：仅允许调用同包已hash登记的payload/check-startup.ps1；输出须通过非秘密JSON/固定错误校验，不得回显原始环境变量、文件路径、credential值或其他stdout/stderr；诊断子进程必须退出，父launcher最终保持失败退出码；诊断脚本缺失、畸形manifest或意外异常时退回固定拒绝文案。
- 验收：hosted Windows runner从实际候选清洁解包根目录启动payload/start-trial.ps1；确认报告显示当前全部信任阻断项、launcher非零退出、正式API/服务/监听均未启动；诊断路径缺失和manifest损坏仍固定拒绝且无环境泄露；候选hash不变，临时子进程清理。
- 回滚：恢复原start_windows_trial_candidate.ps1固定失败文案即可；无API/Schema/Migration/数据变化。
- 执行环境：仅GitHub hosted Windows Runner及D盘RUNNER_TEMP；不在用户本机/C盘运行项目代码。
- 编码前结论：此任务不需要任何真实信任材料或客户数据，可在现有不满足启动条件的候选上完成受限诊断可用性验收；正式信任和正向启动继续保持未验证，当前可实施。


## 首轮 hosted 偏差（2026-10-30）

- Run 40997732541 的基础回归/候选父包/A17均成功；parent smoke job 123877495127 在新launcher验证调用前，触发 NameError: digest_path is not defined。
- 失败点是A33 smoke Harness新增的源诊断脚本hash复核误用了其他模块中的函数名；当前Harness已有本地sha_file(path)辅助函数。尚未对 launcher 行为作出验收结论，不能计A33 PASS。
- 按本条先记录，后续仅将两个测试断言改用本文件既有sha_file，不改变产品launcher、不放宽hash检查；hosted完整重跑后再判定。
