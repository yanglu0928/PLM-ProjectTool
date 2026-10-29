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
