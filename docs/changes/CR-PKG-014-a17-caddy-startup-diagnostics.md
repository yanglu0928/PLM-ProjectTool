# CR-PKG-014：A17 Hosted Caddy 启动失败诊断补齐

- 日期：2026-11-06
- WBS：PLT-PKG-01-A09-P51-A17 Hosted packaged PlanVersion/HTTPS/PostgreSQL 验收
- 状态：PASS_LIMITED（Hosted A17 复验通过；启动失败诊断分支未触发）
- 来源：run [42243433283](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42243433283) 中 A17 job 失败；检查当前 Harness 确认 Caddy 子进程的 `stderr=subprocess.DEVNULL`，导致 `/health/ready` 等待只返回“stderr unavailable”。本次 P40 同进程 Edge 下载与 P39/P24/A50/P25/A34 均独立成功。

## 当前证据与问题

A17 在 packaged parent 候选的隔离验证中，API 检查已进入随后 Caddy HTTPS readiness 阶段。Caddy 进程在 `/health/ready` 之前退出；Harness 把 Caddy stderr 丢弃到 DEVNULL，现有失败信息无法区分端口占用、配置、权限或其他启动故障。此前 run [42220874670](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42220874670) 曾成功，故不先假设是稳定的产品/包缺陷。

## 方案与差异

- A：直接重跑 A17，不补诊断。拒绝：可能再次只得到不可行动的失败原因。
- B：仅在本次 A17 的隔离 run 根中把 Caddy stderr 写入临时诊断文件；在子进程退出时报告退出码，以及有限、固定分类（如 socket bind、access denied、missing file、config failure）；未知输出只报告截断范围内的 SHA-256。原始日志不上传、不打印，run 清理逻辑仍须停止 owned processes 后删除整个 owned temp 根。选择 B。

## 影响、风险、迁移及回滚

- 只调整 Hosted 测试 Harness 和其进度/版本记录；不改产品 API、数据模型、数据库、配置默认值、服务行为、安装器或发布候选。
- 临时日志可能有合成临时路径与地址，仅留于 GitHub Hosted D:\ runner temp 并随 owner temp 根清理；报告不包含原文、headers、请求正文、客户数据或凭据。
- 无数据库/文件迁移、无生产数据操作、无服务安装或正式启动，不读取/建立 License 私钥或生产信任。
- 回滚：恢复 Caddy stderr 重定向至 DEVNULL并移除诊断分类；不影响既有安装包和历史候选。

## 验收计划

1. 先做静态审查：Caddy 日志路径必须是本轮新建 owned run 根的子路径；任何 failure summary 均只报告固定诊断标签、退出码、受限摘要。
2. 在 GitHub Hosted Windows runner 的 D:\ RUNNER_TEMP 运行 A17；确认 Edge HTTPS/PG18 flow 的既有 required markers、子进程停止和全量 owned-temp 清理。
3. 若 A17 仍失败，根据新证据定位下一单一根因；本轮不得以诊断日志 hash 代替 A17 通过。
4. 合成与 Hosted 通过仅为 PASS_LIMITED；不推定 Windows 11 实机、Publisher 信任、Pilot、Gate 或 Release 通过。


## Hosted 复验（2026-11-07）

GitHub Hosted run [42248236859](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42248236859) 全部 jobs 成功。A17 packaged PlanVersion/HTTPS/PG 返回 PASS_LIMITED，运行在 Windows Server 2025 Hosted D:\；输出 Edge HTTPS 创建/读取/校验/提交评审和 PostgreSQL 快照 required markers，合成 PG18 后端写验收通过；候选载荷 20,239 项校验，Owned run root 已清理。P40、P39、P24、A50、P25、A34与前后端/sidecar/父包构建也成功。A34仅为受限合成包替换与人工恢复演练。

这次 A17 成功运行证明新增 Caddy 临时 stderr 捕获没有破坏正常运行与清理；上一轮提前退出没有重现，因此退出码/错误分类分支并未实际触发，不能声称已定位或验证原偶发根因。CR-PKG-014按有限验收关闭，若复发按新日志摘要继续查。

同 run P40 package preflight 仍给出以下 blocker：正式产品公钥未随包、License 正式信任未验证、数据库凭据引用未验证、服务身份 ACL 未验证、TLS 配置未验证；listener 未启动。不得凭此候选开始正式 Pilot、安装或宣称 Gate/Release 通过。Publisher/服务ACL检查在可用受控真实来源缺失时保持阻塞。

### 剩余边界

- 不改产品 API、Schema、权限、服务账号和正式 trust；无 migration。
- 不接触客户资料，不外发外部服务；合成 identities/PG only。
- Windows 11 实机、正式 Publisher/TLS/License来源、生产 ACL、完整客户业务 UAT、Gate 与发行仍未验。
