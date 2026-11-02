# PLT-PKG-01-A09-P51-A44：将非秘密 Pilot 就绪诊断纳入 Windows 候选包（编码前检查）

- 日期：2026-11-02
- 状态：编码前检查完成；实施前偏差/范围记录，尚未修改程序。

## 当前基线与问题

Phase 2 Platform Core；Gate 3、Pilot 和正式 Release 均未通过。A43 当前候选在 GitHub hosted Windows Server 2025 上重建成功，但启动保持 fail-closed，正式公钥/License trust、数据库凭据引用、服务账户/ACL、TLS 等输入不足。

仓库已有 `tools/windows_pilot_readiness_report.py` 和 `tools/validate_windows_pilot_input_register.py`：它们能读取非秘密登记表与包 manifest，并只输出固定状态、缺字段名和阻断码；完整填写也恒为 `pilot_ready=false` 并要求独立验证。但这两个工具没有随 Windows 父包交付，用户需从仓库另找脚本和输入结构，当前候选的只读 startup 报告也没有统一列出登记项。

## 单一目标与实施边界

按 CR-PKG-012 将既有只读就绪报告做成父包内可发现的操作入口：携带现有两个工具和空白非秘密登记模板，提供 PowerShell 5.1 包装命令，并在 README 列明逐字段需维护的引用/证据类型。报告针对当前包 manifest 和用户提供的非秘密 JSON，显示缺项/固定阻断码；无论完整与否都不授予启动、安装、信任或发布资格。

不读取数据库凭据值、License 私钥、API Key、证书私钥、客户正文；不改变启动守门/API/Schema/Migration/License逻辑，不注册或启动服务，不连接数据库。脚本必须在验证外层候选ZIP摘要后再执行；报告写stdout固定JSON，不写用户目录或C盘，不回显用户提交值。

## 验收标准

- 父包在独立 `payload/tools/` 中附带报告器和校验器，并附带非固定字段为 null、固定数据库凭据目标预填的示例登记JSON；父包清单逐文件hash覆盖所有新增文件。
- 包装脚本对包根/目录边界固定定位，调用随包 Python，不接受任意命令/路径；返回结构固定且以非零码表示 incomplete/invalid，但 complete 仍为诊断态。
- hosted Windows runner 对实际组装候选执行：空模板得到所有预期缺字段；合成完整引用得到 `COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION`，`pilot_ready=false`、`launch_authorized=false`；篡改/未知字段拒绝且不回显输入值；候选 hash/原有启动拒绝行为保持正确。
- 全程只使用 GitHub hosted Windows Server 2025 的非 C 盘 runner 临时区；不在本机运行，不推定 Windows 11 新兼容，不更改 Gate/Pilot/Release 状态。

## 风险、回滚与兼容性

将脚本随未签名候选发布存在被误执行风险，因此 README 明确先通过包外SHA-256验证再运行；该入口仅辅助候选审阅，不替代正式代码签名。失败时删除新增 wrapper、工具副本、模板和README条目，恢复原父包构建内容即可；旧artifact与父包摘要保持不变。无数据库/API迁移，旧候选不升级、不覆盖。

## 编码前检查

- 任务只包装已审核的非秘密、只读工具，单一问题为“用户能否在候选包内看到并运行完整的非授权就绪诊断”。
- 固定 CR-PKG-012 的包级入口扩展边界；不增加新的授权、信任源或运行权限。此为方案内落实，不需要另改冻结架构/数据模型/API。
- 源文件需逐一读取并审阅；编码前检查已记录。测试只在 hosted runner 执行；先跑定向测试，随后跑父包组装/启动阻断组合验收。
- 仅合成、非客户的缺项/完整登记输入；GitHub提交前对文档/代码及输出执行 Secret/客户数据检查。

## 首轮 hosted 验收偏差（2026-11-02，run 41373091049）

- 后端全量测试、前端测试/构建、固定来源PG/Python及父包候选组装均成功；D盘 hosted Windows smoke 在调用包内 readiness wrapper 后，空登记场景的 stdout 为空，Harness 在 JSON 解码处失败。尚未获得子进程退出分类，不能判断具体根因，也不能认定A44通过。A35/A17/A34未作为本轮整体成功证据。
- 先记录失败，再只为该子进程加入安全诊断分类（退出码、stdout/stderr字节数，以及固定类别如导入错误/参数错误/解释器启动错误）；不输出原始 stderr、输入路径或登记值。若确认包装器/导入问题，仅修复包内只读报告调用；保持信息不回显、完整登记仍不授权、启动守门不变。
- 下一次以 hosted D盘清洁候选重复缺项/完整/非法三类验收，并要求A44新增验证及父包全部组合job成功后才判PASS_LIMITED。
