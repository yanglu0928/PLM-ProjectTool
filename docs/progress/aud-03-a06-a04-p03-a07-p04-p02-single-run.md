# P03-A07-P04-P02 单次Worker协调

日期：2026-09-26；状态：PASS（已绑定command单次协调；非claim主循环/失败Owner）。

编码前检查：Phase2/P04-P02；前置实际发布恢复/当前授权周期心跳/Worker数据库边界PASS。涉及Audit Application原源只读路径选择与单次协调；无Schema/API/角色/依赖，不claim/分派其他Job，不开放POST。

策略：当前授权/根/原受理pair/实际Job与同代plan/Document登记源选择路径（提示不是权限）。已成功直接受权原源+完整文件Hash重放，不启动续租；未成功有登记文件走原恢复，无登记走capture/render/publish。所有阶段服务重新授权，不覆盖原代暂存/partial；未登记旧字节不能猜Hash，exclusive render失败交给后续重试/新代。

运行：有界周期心跳ready后执行，阶段间check；finally有界stop。stop超时活跃线程不回传成功；operation或heartbeat与提交确认竞争发生错误后，仅在线程实际结束后尝试已有实际Owner recover核验，绝不凭返回DTO/STALE推断成功或将成功Job改回失败。方法不自重置终态/重试/取消，正式失败取消Owner与claim主循环留后续。

验收：严格绑定/路径、已成功不heartbeat、正常capture→render→publish→stop→实际success recheck、失败必须stop/活线程拒绝、确认丢失/成功后STALE仅通过原源恢复；实际PG双Scope空/260 fresh完整链/已登记恢复/并发安全/未登记partial不覆盖、User/取消拒绝与新代。使用专用bounded UOW，正式材料/网络黑洞停机/三平台/质量/Gate/包待。

## 实施与验证

- Changed/Files：Audit `worker_execution.py` 当前授权/原根/pair/同代来源只读路径提示，`run_export_once.py` capture/render/publish或recover+周期ready/check/finally stop+真实source收尾；4分类unit+7协调unit、真实PG validator和状态/决策/版本记录。
- Migration/API/升级：无，head0042；无新角色/依赖/公开HTTP或claim/重试终态写。撤未装配服务保全部历史无需数据迁移。路径提示不是权限或文件存在证明，每次后续操作必须重核当前权限/source/hash。
- 单元：11新增测试实际执行，分类授权先于锁根/结果、缺受理/非法计划/结果无原代计划拒绝、读无业务写；新流程/已登记恢复/成功重放无heartbeat、确认丢失/STALE只通过实际recover、stop timeout仍活跃不恢复或回成功、无源失败安全化与finally stop、无效命令/路径拒绝。
- 实际PG18+专用bounded UOW/当前受权周期线程+临时文件：两Scope空/260真正未capture/未plan/未文件命令完成capture→render→AVAILABLE/Result/Audit/Job原子成功；重复调用13表完全无写。实际已登记stage-only恢复同file；同代完整但未登记旧字节exclusive拒绝/原字节保留、无结果，不猜Hash。实际commit已成功后注入确认丢失，最终根据原成功源返回原FileId并重放无写。真实停用原User在分类前拒绝，无capture/续租/其他业务写。
- 旧发布validator仅增加测试fixture可选capture_source/render_file参数，默认仍原行为；完整旧原子发布/回滚/双Scope/取消锁竞争回归实际执行通过。原有并发成功重放由既有恢复验证覆盖，本轮未新增单次runner同command并发测试，不扩大声明；未新增runner取消/新代独立运行证明，底层既有证明保留。
- Windows11/Python3.13全后端993项无失败，2既有符号链接权限跳过；开发wheel成功585330字节，SHA256 `73e13a5a63fb18b4b06ea26e8cdc5ddab3ce85639bf9b3e9b0b88cf951276591`，非安装交付包。
- Result：单次协调PASS，不代表进程常驻运行。operation错误后只有停止的线程+受权实际来源恢复可以返回成功；活跃stop timeout始终失败。未登记文件拒绝的Job仍RUNNING直到后续正式失败策略/租约接管，不能标已安全收尾。
- Known Issues/Next：P03-A07-P04-P03失败/取消Owner前置核查（当前权撤销、License拒绝时系统终止政策/SystemActor/原根pair和当前Lease、同UOW审计/技术转换、成功禁止复活）；再claim分派与主循环/实际重启及提交Jobs API。网络黑洞停机硬截止、正式账户/三平台/性能/质量/Gate3/UAT与可用包仍待，完整Scope保留。
