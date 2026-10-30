# PLT-PKG-01-A09-P51-A35：Windows 11 父包候选隔离替换演练结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（Windows 11 Home 中文版 build 26300，本机 D 盘隔离候选演练）
- GitHub Actions：[run 41026213054](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41026213054)，12/12 jobs success；A35 handoff job `123968232347` success。
- 工作流代码提交：`e8339aa5d4d72bef562daecb787112cfdbdbb1dc`；新父包来源提交 `7c3e083dd558c0b50b4f2ebf8da0c658043bf699`。
- 本机身份：系统 API 返回 `Microsoft Windows 11 家庭版 中文版`、版本 `10.0.26300`、build `26300`、SKU `99`。注册表 `ProductName` 的 Windows 10 旧字符串未作为 OS 判断依据。
- 执行目录：源码在 D 盘项目目录；下载块、重组包、TEMP/TMP/RUNNER_TEMP、解包和演练根均位于 `D:\A35Temp`；没有把项目代码或临时文件放到 C 盘。

## 验收证据

- A35 hosted handoff 从 A31 旧父包 artifact `12951373170` 与本次 run 当前父包 artifact `12962020334` 生成 8+8 个独立摘要绑定分块。16/16 GitHub Artifact ZIP 摘要逐一匹配远端声明值；重组工具逐块核验 SHA-256、顺序、完整性和同包 `verification-summary.json`。
- 旧包完整 ZIP SHA-256 `f4d417998ba18bb340fb3d39d83a5c356ac73109a894c1f214852f6b72ed4d49`，20,119 个清单载荷文件；新包完整 ZIP SHA-256 `94700239dc2218466087fd4beec90f9d34cd4a6c96ceed1049033df58342e2f2`，20,119 个清单载荷文件。新包 provenance 为 workflow run `41026213054`。
- 在 Windows 11 上以 A34 原演练器完成真实父包初装、替换、失败注入、失败版隔离和显式手动恢复；新版本只在用户选择恢复时恢复旧版本。data/config/license/plugins 四类合成持久标记 4/4 保持，`provenance/` 保留在隔离包中。
- 最终 launcher 仍返回 `BLOCKED`、exit 1；六项阻断码与 A33 固定安全行为一致，service、产品 API、listener 均未启动。`release_eligible=false`、`legal_clearance=false`。
- Windows 11 本机定向测试：A35 分块交接 5/5，A34 替换/恢复 4/4；真实父包整链结果保存在该轮 D 盘隔离记录。hosted workflow 整体12/12 jobs成功。

## 实施偏差与处置

- A34 的 hosted Windows Server 2025 不能证明 Windows 11 行为，因此 A35 使用本机系统 API 已确认的 Windows 11，但所有源码/临时写入/包操作都固定 D 盘。
- 约373 MB的大 Artifact 经 GitHub 文件连接器下载时返回 `Transport closed`；本机 Git 凭据没有 Actions artifact 读取授权。没有转存或提升凭据权限。已登记并新增 `tools/transfer_parent_candidate_chunks.py` 与最小只读 hosted handoff job，将两包各拆为8个、每个不超过50,000,000字节的SHA绑定分块。
- 文件传输曾因中断产生部分文件，采用断点续传后以 GitHub Artifact API 声明的完整 ZIP SHA 复核；一次分块 Artifact ID 与旧/新前缀映射错误立即被 SHA 检查拒绝，未交给重组或运行。16块重取后全部匹配。
- 首次本机演练没有传入 A34 当前候选所属的 hosted `GITHUB_RUN_ID`，故该次不能形成验收；随后按来源 run `41026213054` 补齐上下文重新执行并通过。失败残留仅在 `D:\A35Temp` owner-token staging 中发现并按已核验的精确 D 盘直接子目录清理。

## 限制

- 该结果证明 Windows 11 Home build 26300 上非发行父包的 D 盘隔离替换与显式恢复；不代表其他 Windows 11 edition/build、Windows Server 2025 新验、正式 C 盘安装、物理断网、重启升级或真实用户环境。
- 正式产品公钥/License trust、数据库凭据、服务账户 ACL、TLS、真实正向启动、用户验收、Gate 3～7 与正式 Release 仍未通过。Pilot 继续 NOT_READY；本轮 launcher 保持安全阻断，没有伪造可用状态。\n