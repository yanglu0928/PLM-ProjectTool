# PLT-PKG-01-A09-P51-A35：Windows 11 父包候选隔离替换演练编码前检查

- 日期：2026-10-30
- WBS：`PLT-PKG-01-A09-P51-A35`
- 状态：编码前检查完成，开始 Windows 11 目标机实测。
- 上一项：A34 hosted Windows Server 2025 PASS_LIMITED；run `41020308619`。
- 目标机：系统 API 返回 `Microsoft Windows 11 家庭版 中文版`，版本 `10.0.26300`、build `26300`、SKU `99`；D: 可用约328.8 GB，C: 可用约13.8 GB。

## 范围与安全边界

- 在本机 Windows 11 上复用 A34 已通过的父包候选替换/显式恢复演练器，仅验证 Windows 11 实际 PowerShell、文件系统、路径及 launcher fail-closed 组合。
- 两份输入固定为同仓库 GitHub Actions 非发行父包 artifact：旧版 run `40995913354` / artifact `12951373170`，当前版 run `41020308619` / artifact `12962020334`。每项 artifact 先核对 GitHub 声明 SHA-256，再在 D: 解压和逐文件清单验证。
- 所有 ZIP、解压、测试临时文件与 Python 临时目录固定在 `D:\A35Temp`；工作区源码由 `D:\AI工具\PLM项目实施辅助工具` 读取。C: 不作为工作目录、下载目录、TEMP/TMP、RUNNER_TEMP 或安装目标；不写 `C:\PLMTool`，不触碰系统服务/正式数据库/客户数据。
- 只在随机、任务专属的 D: 临时根执行候选替换、合成标记保全、故障注入和显式恢复；产品启动仍预期 BLOCKED/exit=1，不建立真实服务、数据库或监听器。
- 本机有 Windows 11，但为 Home 26H2/build 26300；结论限定该具体版本和当前用户/D: 文件系统，不外推到 Windows 11 企业版、Server 2025、Debian 或全量离线安装/重启。

## 编码前检查

- 输入为已由 GitHub Actions 验证并留存的两个同仓库 artifact；本 WBS 不重打包、不修改产品代码、Schema、API、License 或正式安装语义。
- A34 演练器只要求 Windows、D: 的 ASCII `RUNNER_TEMP`、TEMP/TMP一致及经验证的 staging 输入。目标机可通过新 Python 子进程环境显式将这些变量指向 `D:\A35Temp`，无需改写工具实现。
- 传输前置偏差已记录：Codex GitHub Artifact 下载工具对约373 MB父包连续返回 `Transport closed`；本机Git凭据能查询GitHub但下载端点返回401，且不具 `actions:read`。不将凭据/Token转存或提升权限。为维持本机轻量目标，拟在已有最小权限 hosted workflow 中下载已验证候选、按50,000,000字节拆分成8块，每块独立Actions Artifact并携带完整包/分块摘要及原 verification summary；Windows 11 只将这些小块下载至D盘、按摘要校验后重组，再运行同一A34演练器。
- 先在 D: 运行 A34 专项测试，再运行两份 artifact 的实际解包、替换/失败隔离/手工恢复和 launcher 检查；任何路径越界、Artifact SHA/内部 manifest/hash 不符、临时目录清理失败或启动不符合预期，均判失败并停在隔离目录内。
- 验收边界：A35 可增加 Windows 11 实机的隔离文件系统/PowerShell 证据；这仍不等同正式安装、服务账户 ACL/TLS、物理断网、真实信任、业务启动、重启/升级、UAT 或 Pilot/Gate/Release 通过。

## 差异记录

- A34 只在 hosted Windows Server 2025 执行，无法代表 Windows 11。此前置检查新增一次使用现有 Windows 11 目标机、但将全部任务输入和临时数据留在 D: 的验证切片；这是验收环境补充，不改变冻结产品基线或 Release 判定。
- Windows 11 本地重跑 A34 四项合成定向测试均通过（Python 3.13、TEMP/TMP/RUNNER_TEMP=`D:\\A35Temp`，4/4，0.364s），证明当前工具单测可在目标OS执行。尚未运行真实父包替换；大Artifact传输失败，实施小块云端交接后再继续。该限制不算包验收通过。
