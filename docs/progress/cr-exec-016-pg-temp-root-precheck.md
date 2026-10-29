# CR-EXEC-016 编码前检查：A17 nested PostgreSQL 临时根

- 日期：2026-10-28
- 唯一问题：包内 PostgreSQL smoke 继承 P42 负向目录 ACL 夹具作为系统 temp，导致 initdb 不能创建数据目录。
- 证据：run 40650259852 的日志为 PLMToolTemp/plm-p42-platform-write-<随机>/pgdata Permission denied；所有路径映射、候选构建和父包 PG smoke 已通过。
- 实施方向：A17 上优先使用已验证的 PLM_P51_TEMP_ROOT，创建唯一命名的直接子目录作为 DB data root；其他调用 fallback 系统 temp。清理时沿用同一个显式选定 root 并确认对象归本次调用。
- 验收：路径选择单测与 hosted Windows A17 bundled initdb/migration/cleanup full flow。
- 回滚：移除 A17 root 覆写，恢复系统 temp，保留 A17 failed run。
- 数据：合成 PostgreSQL；不连接外部或现有数据库。

- 2026-10-28 云端 run 40652307366：新增 A17 temp-root 静态边界检查 PASS；后端 3849 项单测有 1 项既有并发测试 ready.wait(3) 偶发超时，其余基线组件 job 成功、打包/A17依赖任务跳过。已登记 CR-EXEC-016；完整重跑待证，不把该 run 记为通过。

- 2026-10-28 hosted run 40652933457：后端 3849/3849、前端、PG18/pgvector、embedded backend 与 parent candidate 构建通过。新增路径单测 fixture 使用默认 C 盘系统 temp，正确被边界规则拒绝；已记录为测试夹具错误，修改夹具使用 RUNNER_TEMP 的独立子目录后重跑。A17 full flow 因投影检查失败未运行。

- 2026-10-28 hosted run 40654144099：后端3849项、前端、运行时组装、父包和A17候选投影、父包PG smoke全部通过；A17真实链仍在 `smoke_packaged_platform_write_https.py` 的 PG initdb 失败。路径显示 temp_root 被 P42 负向 ACL 夹具设为 `plm-p42-platform-write-*`。已将 CR-EXEC-016 扩展至该嵌套 smoke：A17 优先用 PLM_P51_TEMP_ROOT，非 A17 保留 PLM_TEST_TEMP_ROOT fallback。不能记 PASS。

- 2026-10-28 hosted run 40656184670：CR 临时根选择单测、父包 PG smoke均通过，但 Platform Write nested smoke 仍把 PG `pgdata` 写在 P42 `plm-p42-platform-write-*` 目录并收到拒绝。扩展方案：独立创建 sibling PostgreSQL 临时目录，不与 P42 专用权限工作目录共用；重新执行 A17。

- 2026-10-28 hosted run 40659216063：候选投影与父包 PG smoke PASS，A17 initdb 在 PLMToolTemp 子树中继续 Permission denied。已将 CR-EXEC-016 最终路径调整为 A17 owned root 内 PLMPostgresTemp sibling，和 P42 受限 PLMToolTemp 分离。A17 仍未通过。

- 2026-10-29 hosted run 40662516205：全量 backend、frontend、运行时/父包组装、候选投影与 parent PG smoke 通过；A17 在 Platform Write smoke temp-root 前置断言失败。已登记：general temp 与 PostgreSQL temp 变量误混，修正后重跑 A17。

- 2026-10-29 hosted run 40794073885：全量回归、候选、父包 PG smoke 和 A17投影通过；A17 initdb 在 owned run-root 内的新 PG temp 子树仍被拒。已登记再次修正：PostgreSQL root 移至 RUNNER_TEMP 下与 A27 run-root 同级且按 GITHUB_RUN_ID 精确绑定的子目录；完整重跑待证。


- 2026-10-29 hosted run 40796767823：基础 7 个任务通过，含父包 PG18/pgvector 临时生命周期；A17 8 项投影单测因越界路径夹具未创建而 1 项错误，full flow skipped。已登记并在 CR-EXEC-016 修复夹具后重跑；不得记为 A17 通过。


- 2026-10-29 hosted run 40798104759：9/10 jobs 通过；A17 实际进入 initdb，仍因 PostgreSQL root 下多层目录 ACL Permission denied 未能创建 pgdata；父包同 runner 的独立 PG18 smoke 通过。已按 CR-EXEC-016 改为直接 RUNNER_TEMP root、smoke 独占随机 PG 子目录并自行清理，禁止 wrapper 删除 RUNNER_TEMP；完整 hosted A17 重验待证，WBS 未通过。


- 2026-10-29 hosted run 40799723167：9/10 jobs通过；A17 initdb 在直接 RUNNER_TEMP 创建的随机 PostgreSQL 工作目录下仍 Permission denied，证明只改 temp root 不够。新增 CR-EXEC-016 子进程隔离：PG 子进程只使用其自身 pg_run 作为 TEMP/TMP，避免继承 P42/布局 smoke 临时变量；下一轮重验。


- 2026-10-29 hosted run 40801427817：9/10 jobs通过；A17 initdb 在直接 RUNNER_TEMP 的唯一随机目录下仍无法创建 pgdata，即使其TEMP/TMP已隔离到同一 pg_run；证据否定“只改进程临时变量即可解决”。下一次将由 smoke 先创建并验证空 pgdata，再交 initdb 初始化；CR-EXEC-016和状态记录已更新。


- 2026-10-29 hosted run 40802934467：9/10 jobs通过；Python预建空pgdata后，Windows initdb改报File exists，确认该方案不兼容并已撤销。新方案在随机owned pg_run上对hosted当前账户授予继承权限，initdb目标保持不存在；授权失败则fail-closed，待完整云端验证。


- 2026-10-29 hosted run 40804340056：9/10 jobs通过；A17已越过initdb/PG启动/migration/API readiness，Caddy validate启动时CreateProcess FileNotFoundError。PG ACL调整已将阻塞推进到下一阶段；检查Caddy文件/受限PATH/SystemRoot，加入Caddy runtime目录后进行完整A17重验，Edge/PlanVersion与最终清理尚未通过。
