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
