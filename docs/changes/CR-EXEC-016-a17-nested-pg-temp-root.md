# CR-EXEC-016：隔离 A17 嵌套 PostgreSQL smoke 临时数据根

- 日期：2026-10-28
- 状态：实施中
- 来源：A17 已通过包路径映射，进入 bundled PostgreSQL migration 后，initdb 在嵌套 P42 平台写入边界测试专用临时目录创建 pgdata 失败。
- 云端证据：hosted run 40650259852 的 A17 job 日志显示目标位于 PLMToolTemp/plm-p42-platform-write-<随机>/pgdata，initdb 返回 Permission denied；上一层目录由 P42 负向权限夹具管理。
- 目标：A17 runner 下的数据库 smoke 显式创建随机直接子目录于 PLM_P51_TEMP_ROOT，避免继承被当前 P42 负向测试替换的 tempfile.gettempdir；非 A17 调用保留系统临时根。仍只操作 owned 临时数据，所有权及清理检查以选定 root 为准。
- 基线差异：测试夹具运行期临时路径选择；不改产品数据路径、打包内容、Schema、DB 凭据、生产服务或安装逻辑。
- 风险：临时根选择错误可能误删外部路径。限制为环境明确指定的 A17 root 后代、目录名固定前缀、路径真实解析和 fast-stop 验证后仅清理由本次调用创建的数据目录。
- 回滚：恢复使用系统 tempfile 根并保留失败证据；不触及用户数据。
- 验证计划：定向测试验证 A17 root 优先且创建目录为其直接子目录、非法 root 拒绝；hosted A17 full flow 必须完成 initdb、migration、Edge markers、PG state and cleanup。未达 markers 不记 PASS。
- 安全：只在 hosted runner 的 D 盘 synthetic temp 运行，不使用本机资源、客户资料或 Secret。

- 云端验收追加（run 40652307366，SHA `c306232b9c1f4eeed3456f9646099f68c858e2a1`）：路径边界检查通过；全量后端 3849 项中仅既有并发用例 `test_stop_waits_for_current_probe_before_marker_and_db_release` 在 3 秒 ready 等待处超时，其余下游 A17 jobs 因后端 job 失败而跳过。该结果不归因为本变更，需完整重跑以确认是否为 runner 抖动；当前 CR 未验收。

- 云端验收追加（run 40652933457）：后端 3849 项、前端、PG18/pgvector、embedded backend、父候选构建均通过；候选投影前的 8 项单测有 1 项夹具失败。测试把模拟 RUNNER_TEMP 放进系统 C 盘临时目录，触发实现的非 C 盘保护。修正单测改用 hosted `RUNNER_TEMP` 中的唯一目录；该 run 的 A17 full flow 未执行，不计 CR 通过。

- 范围修订：A17 嵌套链不止 `smoke_packaged_pg18_migration.py`，还由 `smoke_packaged_platform_write_https.py` 在 `PLM_TEST_TEMP_ROOT` 指向的 P42 负向 ACL 目录下创建独立 PG 集群。选择复用已经验证的 `PLM_P51_TEMP_ROOT` 作为该 smoke 的优先 temp 根；旧 `PLM_TEST_TEMP_ROOT` 保留为非 A17 fallback。run 40654144099 的 initdb 仍在负向目录收到 Permission denied，证明此前实现未覆盖完整调用链。迁移/业务数据不变，仍只操作此 smoke 创建的临时目录。

- 云端验收追加（run 40656184670）：基础 jobs、3849 后端测试、父包、候选投影与父包 PG smoke 全通过；A17 仍在 `PLMToolTemp/plm-p42-platform-write-<id>/pgdata` 被拒。现确认只替换根变量仍让 PG cluster 放入 P42 专用目录。实施范围进一步细化：将 PG cluster、日志和 dump 改放同一 owned PLM_P51_TEMP_ROOT 下的 sibling `plm-pg18-platform-write-*`，P42 专用目录继续承载其自身受限工作文件；清理分别校验两条路径的归属和前置进程退出。回滚是将 cluster 路径恢复到旧 `run`，测试数据无迁移。

- 云端验收追加（run 40659216063）：基础全量链、父包 PostgreSQL smoke 成功；A17 仍显示 `PLMToolTemp/plm-pg18-platform-write-*/pgdata` 被拒，表明 P42 负向 ACL 作用于整个 `PLMToolTemp` 子树，简单 sibling 不足。最终隔离方案：runner wrapper 在独立 owned run-root 下创建 `PLMPostgresTemp`，与 `PLMToolTemp` 同级；通过 `PLM_PG_TEMP_ROOT` 限定给内层 PG smoke，校验其直接位于 `RUNNER_TEMP/plm-p51-a27-<run>/PLMPostgresTemp`、D 盘、ASCII、非 symlink。A17 结束时移除整个已验证 run-root；单体 smoke 对自己创建的数据目录仍按停库后清理。回滚恢复先前 PG 根来源。

- 云端验收追加（run 40662516205）：完整基线和 parent PG smoke 通过，A17 在 `smoke_packaged_platform_write_https.py` 入口目录校验失败。根因是上次将该 smoke 的 general temp_root 选择改为 `_migration_temp_root()`；现在该 helper 优先返回 PLMPostgresTemp，但入口仍要求 PLMToolTemp。修复为 general artifacts 显式优先读取稳定的 PLM_P51_TEMP_ROOT（PLMToolTemp），独立 PostgreSQL cluster 继续使用 PLM_PG_TEMP_ROOT（PLMPostgresTemp）。数据/安装逻辑不变，回滚恢复原 selector；A17 需全量重验。

- 云端验收追加（run 40794073885）：A17 入口变量已正确区分，但 initdb 在 owned run-root 下 `PLMPostgresTemp/plm-pg18-platform-write-*/pgdata` 仍 Permission denied；父包 PostgreSQL smoke 在 runner temp 验收通过。CR 实施路径再调整为 `RUNNER_TEMP/plm-p51-a27-pg-<GITHUB_RUN_ID>` 直系子目录，以 run id 绑定、非 C 盘/ASCII/非 symlink校验；平台 smoke 临时材料继续位于 owned run-root 的 PLMToolTemp。A17 wrapper 成功收口时先确认 PG root 是本 run 直系子目录并清理，再移除 run-root；失败日志保留本次临时证据供 runner 生命周期回收。合成数据，不连接已有/外部数据库。


- 云端验收追加（run 40796767823，commit `c49407e28c1b5a3ddd08ed2b10e0015c6e9ff69f`）：基础边界、后端、前端、Python、PG18、embedded backend、父包组装和父包 PostgreSQL 生命周期 smoke 成功。A17 候选投影的 8 项测试中有 1 项负向路径夹具错误：模拟 `outside` 目录未先创建，Windows `Path.resolve(strict=True)` 先抛 FileNotFoundError，导致完整 A17 跳过。已定位为测试夹具问题，修复为创建越界模拟目录后验证拒绝；A17 full flow 尚未运行，本轮不计通过。


- 云端验收追加（run 40798104759，commit `78f406632329aa5bef0717b6d5aee73bebefccf9`）：10 个 hosted jobs 中 9 个通过，含 3849 后端全量回归、前端、运行时/父包组装、A17 投影、父包 clean extraction 与独立 PG18/pgvector 生命周期；A17 packaged flow 实际启动但 initdb 在 `RUNNER_TEMP/plm-p51-a27-pg-<run>/plm-pg18-platform-write-<id>/pgdata` 返回 Permission denied。失败发生在 P42 后续业务检查之前，未产生 Edge/PG PASS marker，不能关闭 A27。

- CR-EXEC-016 实施调整（依据 run 40798104759）：再增加 RUNNER_TEMP 中间目录仍触发嵌套 ACL 拒绝，而同轮父包 PG smoke 直接在 RUNNER_TEMP 建立唯一临时目录并完成 initdb/迁移/停库/清理。最小调整为 `PLM_PG_TEMP_ROOT` 必须解析为本轮 hosted `RUNNER_TEMP` 本身，由既有 smoke 用随机、固定前缀的直接子目录承载 PG cluster，并在进程确认停止后删除该子目录；A27 wrapper 只删除自己拥有的独立 run-root，明确不删除 RUNNER_TEMP。所有数据仍为 synthetic，runner 结束提供最终隔离回收。验证包含路径边界单测、完整 A17 包内 Edge/HTTPS/PG marker、临时数据库停止和目录清理。

- 风险与回滚：RUNNER_TEMP 是较宽的临时工作区，因此 smoke 必须只创建并清理自身随机命名的 `plm-pg18-platform-write-*` 子目录，wrapper 禁止递归删除 RUNNER_TEMP；如 A17 仍失败，保留 hosted run 日志并回滚到 CR-EXEC-016 前一版路径选择，继续诊断，不放宽正式产品 ACL。


- 云端验收追加（run 40799723167，commit `502e5cb2a2ccf1df3e7e9e3e4245df04d15b5def`）：修复投影夹具后 9/10 jobs 通过，A17 再次在 initdb 创建 `RUNNER_TEMP/plm-pg18-platform-write-<id>/pgdata` 时 Permission denied；目录根已直接使用 RUNNER_TEMP，说明单纯改变路径深度未解决问题。父包独立 PG smoke 在干净进程环境通过。

- CR-EXEC-016 实施调整：A17 wrapper 为边界验证和安装/布局 smoke 将 `TEMP/TMP` 指向 PLMToolTemp，该目录可能经历负向权限验证；嵌套 PostgreSQL 命令此前继承这组临时路径。现在 initdb、pg_ctl、pg_dump/pg_restore 使用移除 PLM 环境覆盖后的专用子进程环境，并把 `TEMP/TMP` 指向本 smoke 自己的随机 `pg_run`。PG data/log/dump 仍限定于本 smoke 子目录，停库且确认进程退出后清理。回滚为去掉 PG 专用环境、恢复继承调用方 TEMP/TMP；不改产品运行时或 ACL。通过 hosted Windows A17 full flow 验证实际权限和清理。


- 云端验收追加（run 40801427817，commit `d9985c8e36625a22dc5212144221a06da1295b66`）：9/10 jobs通过，A17 仍在 initdb 创建 `RUNNER_TEMP/plm-pg18-platform-write-<id>/pgdata` 时 Permission denied；PostgreSQL 子进程已使用 `pg_run` 专用 TEMP/TMP，故临时变量继承假设未获支持。父包 PG smoke、A17投影和其他全量组件通过；业务marker未产生。

- CR-EXEC-016 进一步收敛：让 smoke 自身先校验 `pgdata` 不存在，再在唯一 `pg_run` 内创建并验证空目录，交由 initdb 在该空目录初始化（PostgreSQL initdb 接受现存空目标目录）。不改变父级临时根、产品数据或权限策略。若 hosted 验证失败，保留错误输出并退回前版实现继续定位；空目录仍只在 PostgreSQL 进程确认停止后清理。

- 云端验收追加（run 40802934467，commit `cd7954cc20036c5bc285d785eaab6ee9ec68cf9e`）：9/10 jobs通过。预建空目录后 initdb 从 Permission denied 转为 `File exists`，证明 Windows 版 initdb 要求目标路径尚不存在；预建方案撤销。PG直接目录和子进程TEMP/TMP均已隔离，A17其余链未执行通过marker。

- CR-EXEC-016 实施调整：保持 data 目标不存在，由 Python 对本轮唯一随机 `pg_run` 解析 hosted 当前账户并用 `icacls` 在该目录显式授予仅继承至其内容的完全控制，再运行 initdb。授予前校验目录真实存在且不是 symlink，账户名经过字符白名单，不使用 shell，icacls失败时停止并保留诊断。权限范围只有 synthetic smoke 临时目录，PG完成后仍按进程退出/目录归属检查清理；不修改系统目录或产品数据ACL。验证计划为完整 hosted A17，以及权限授予、Edge/PG markers 和清理结果。

- 云端验收追加（run 40804340056，commit `a3e72ed0204b03cc84d20eafea2268504a5191d3`）：9/10 jobs通过，A17通过 initdb/PG启动、bundled migration 与 packaged API readiness，进入 Caddy validate；Windows CreateProcess 抛 FileNotFoundError。PG 权限阻断不再复现，空 data 目录验证保持未预建状态；A17 的 Edge/PlanVersion业务 markers尚未产生。

- CR-EXEC-016验证结论：在仅 owned 随机 `pg_run` 为 hosted 当前账户授予继承ACL后，PostgreSQL 初始化、启动、migration及产品API readiness到达。临时ACL方案部分验证成功，仍需整个 smoke 清理证据。新增次级修正：将 Caddy 自身目录纳入受限 smoke PATH，显式确保 SystemRoot/WINDIR，且在CreateProcess前验证 Caddy可执行文件存在；不改产品发行配置。Hosted full flow重试须到 Edge 和 PG state markers、临时数据库停止及目录删除才可关闭 CR。
