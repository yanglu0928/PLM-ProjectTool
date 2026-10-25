# PLT-PKG-01-A08-P09-P05-P03-A06-P03：多格式模块采样与 ETW 前置

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A06-P03`；只验证 A05 非发行候选在更多图像格式下的运行模块路径，并检查系统级 LoadImage 跟踪是否可用。
- 输入基线/前置：CR-PKG-003、A06-P02 静态/延迟导入图、固定 Tesseract5.5.3 MSYS2 隔离目录与合成中文 PNG。Gate 2 已通过，Gate 3 未通过。
- 模块/实体/API/权限：新增仅在 Windows 本机运行的观察脚本；无产品 Parser、ORM/Migration、API、权限、正式安装与候选包组成修改。
- 验收：可重复记录进程退出、采样次数、随包/系统/意外模块路径；PNG、TIFF、JPEG 图像命令实际运行；ETW 若权限不足明确保留盲区，不以周期采样冒充完整跟踪。
- 风险/回滚：采样会漏短暂加载，合成图像不覆盖所有格式/插件/生产输入；生成文件均在 Git 忽略的本机目录，旧候选不变。

## Windows 11 结果（2026-10-01）

本机账户的 Administrators 组为 `deny only`。`Microsoft-Windows-Kernel-Process` Provider 可查询 `WINEVENT_KEYWORD_IMAGE=0x40` / `ImageLoad`，但以唯一会话名执行 `logman start ... -ets` 返回 `Access is denied`；ETW 会话未建立，无 ETL 或完整事件流，不将其记为通过，也不绕过提权边界。后续在经授权的目标管理员环境独立执行系统级 LoadImage 跟踪。

`tools/observe_tesseract_windows_modules.ps1` 使用隐藏的隔离 CLI 子进程，约20 ms 周期读取 `Get-Process -Module`，输出 `release_eligible=false` 的 JSON。固定合成中文 PNG 及由它生成的 LZW TIFF/JPEG 三种输入分别执行 `chi_sim+eng`：

| 输入 | 退出码 | 成功采样 | 随包模块 | System32 模块 | 其他路径 |
|---|---:|---:|---:|---:|---:|
| PNG | 0 | 10 | 35/35 | 23 | 0 |
| TIFF | 0 | 12 | 35/35 | 23 | 0 |
| JPEG | 0 | 12 | 35/35 | 23 | 0 |

本机证据分别位于 Git 忽略的 `artifacts/package-prep/windows11/tesseract-msys2-observe-{png,tif,jpg}-a06/module-observation.json`，输入 Hash 和过程输出均保留本机，不推送二进制/运行日志。依据 [Microsoft 运行时动态链接说明](https://learn.microsoft.com/en-us/windows/win32/dlls/run-time-dynamic-linking)及[DLL 安全建议](https://learn.microsoft.com/en-us/windows/desktop/dlls/dynamic-link-library-security)，周期性已加载模块列表不能替代完整 LoadImage 跟踪或所有代码路径验证。

对已存在输出目录重跑被拒绝，原 `module-observation.json` SHA-256 未变化；没有覆盖前轮证据。

本项完成的是 `THREE_FORMAT_SAMPLED_ONLY`；ETW/短时加载、其他输入格式、正式只读 ACL/服务账户、许可证与签名、真实质量、Server2025 仍未通过，`release_eligible=false`。下一项转入不依赖提权的发行许可证义务和通知清单核查，ETW 留作目标环境前置。
