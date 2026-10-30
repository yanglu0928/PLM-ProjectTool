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


## 第二轮 hosted 偏差：PowerShell launcher 调用超时（2026-10-30）

- Run 41000446225 的全量构建、后端/前端、运行时与父包组装成功；parent smoke job 123886741768 在probe_packaged_startup_guard调用实际payload/start-trial.ps1时，PowerShell 5.1进程超过20秒并触发subprocess.TimeoutExpired。stdout/stderr/退出码未取得。
- 此次失败由测试超时证据触发，不能认定是单纯CI抖动，也不能视为产品安全或诊断通过。A17为独立并行job且已成功。
- 先记录，再仅调整launcher的诊断子进程启动/有界读取与测试超时/超时证据输出；保持子进程只运行已hash校验的只读诊断，launcher最终失败关闭，异常仍不泄露环境内容。后续用D盘hosted runner重新验证实际诊断及缺失/损坏输入。


## 第三轮 hosted 偏差：launcher 仍回退固定文案（2026-10-30）

- Run 41002269359 在托管 Windows Server 2025、D:\\a\\_temp 上完成后端/前端、运行时、父包组装与 A17 job；parent smoke job 123891914452 在launcher调用后失败，异常为“did not forward a JSON preflight report”。新15秒子进程界限阻止了此前20秒无界等待，但本次无JSON输出；现有Harness未打印子进程退出码及输出字节分类，尚不能确定launcher内部哪条校验触发固定回退。
- 不将超时改善误判为A33通过。先记录，再仅增强Harness报告的非敏感执行分类（退出码、stdout/stderr字节数及是否命中固定拒绝文案），不输出原始环境或路径；据新hosted证据调整launcher的进程启动/输出处理，保持固定fail-closed及15秒上限。


## 第四轮 hosted 偏差：launcher 固定回退分类（2026-10-30）

- Run 41003355111 / parent smoke job 123895263737 在 D:\\a\\_temp 清洁解包 Windows Server 2025 runner 上仍未转发报告；Harness分类为 exit=1、stdout=0字节、stderr=72字节、命中固定拒绝文案。launcher已在15秒内结束，证明未复现先前20秒超时，但其内部catch隐藏了子进程/报告校验的具体阶段。
- 结果仍不能计A33通过。先记录，再仅加受限、静态的诊断失败阶段标识用于云端Harness定位；不记录异常正文、环境变量、路径或凭据值，默认用户输出仍是固定拒绝文案，15秒子进程上限和拒绝启动行为不变。


## 第五轮 hosted 偏差：诊断校验清单路径正则误转义（2026-10-30）

- Run 41004441473 / parent smoke job 123899012018 的白名单阶段码显示launcher失败发生在 `VALIDATE_INPUT`，stdout为空、stderr为固定拒绝+阶段码，exit=1；没有超时或泄露。
- 逐项检查代码发现两个checksum行正则用了双反斜杠 `\\\\.`，在PowerShell正则字符串中会尝试匹配反斜杠而非转义文件名点号，故未匹配 `payload/check-startup.ps1` 路径，触发预期fail-closed回退。
- 此偏差在A33子进程实现引入；先记录，再只将两处regex修回单反斜杠 `\\.`。保留父清单整体SHA和文件SHA双重校验、不改变manifest/安全判断，再跑Windows hosted完整复验。


## 第六轮 hosted 偏差：修复正则后仍在输入校验阶段回退（2026-10-30）

- Run 41005582706 / parent smoke job 123902165877 在托管 Windows Server 2025 的 D:\\a\\_temp 清洁解包目录复验。后端/前端、PG18/pgvector、嵌入式运行时、父包组装及 A17 投影候选 job 均成功；启动launcher仍为 exit=1、stdout=0字节、stderr=108字节，阶段码 VALIDATE_INPUT，未超时、无服务启动或敏感输出。
- 上一轮记录的regex修正已进入提交 e472af3e3e697de658b6b30f4a75429df5d88790，但仍未能转发诊断JSON，故上一轮修复不足，A33依然未通过。现有证据只能定位到输入校验，不足以认定仍是该正则原因。
- 按纪律先记录本次失败，再只读核查实际校验输入、PowerShell匹配语义与打包脚本对应关系；随后提出更窄修复，保持清单哈希、逐文件哈希、非零退出、缺失/损坏回退及不启动服务条件。必须再次以同一托管路径验收。

- 同一提交另一次独立重复运行 Run 41005586483 / job 123902482913 也以相同的 exit=1、stdout=0、stderr=108、VALIDATE_INPUT 失败；其余构建/投影工作继续成功。此重复证据排除一次性运行抖动，但不增加新的根因判断。


## 2026-10-30 诊断阶段细分改动自审发现遗漏

- 为定位此前两次 hosted VALIDATE_INPUT，提交 610e7af 将单一输入校验阶段拆为静态子阶段。提交后代码自审发现编辑器在重新排列阶段标签时遗漏了实际 `$checksumsDigest = Get-FileHash(...)` 赋值，导致验证表达式读取未定义变量并始终安全回退。该提交尚未获得 hosted 结果；发现后立即暂停其验收结论，不计A33 PASS。
- 该为本任务源码的本轮实施错误，不涉及用户数据或服务启动。先登记再修复：恢复哈希赋值，保留已验证的正则与细分阶段码；继续以差异/Secret检查后进行同一托管清洁解包复验。回滚为将标签细分恢复至单一阶段并保留哈希赋值；所有失败路径仍拒绝启动。
