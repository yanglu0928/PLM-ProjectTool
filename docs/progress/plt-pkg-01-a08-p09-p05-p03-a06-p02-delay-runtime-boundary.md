# PLT-PKG-01-A08-P09-P05-P03-A06-P02：延迟导入与运行时加载边界

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A06-P02`；仅扩展非发行 Tesseract PE 审计与隔离观察。
- 输入基线/前置：CR-PKG-003、A05 35 本地 PE 候选、A06-P01 来源/许可文本矩阵。Gate 2 已通过，Gate 3 未通过。
- 模块/实体/API/权限：审计器、候选构建器和定向合成测试；不改产品 Parser、正式依赖、ORM/Migration、API、权限或安装路径。
- 验收：依据 [Microsoft PE 格式说明](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)解析 AMD64 延迟导入描述符并拒绝坏属性；重新构建候选的文件集合与 A05 完全一致；在一个实际 OCR 进程采样已加载模块，区分随包与系统模块。
- 风险/回滚：静态表与周期性采样都不能证明所有输入路径或短暂 `LoadLibrary` 行为；可撤新审计代码/新隔离目录，A05 候选与原官方安装资产不变。

## Windows 11 证据（2026-10-01）

`tools/audit_tesseract_runtime_dependencies.py` 现在同时读取普通及延迟导入，支持 AMD64 PE 的 RVA 形式、拒绝未定义属性与异常指针。候选 35 个 PE 的延迟导入边数为 0，普通+延迟闭包仍为 35，根目录无多余 DLL。`tools/build_tesseract_msys2_poc.py` 同步以两类导入的并集装配；全新 ASCII 目录 `C:\Users\17231\AppData\Local\Temp\plm-tesseract-msys2-delay-20261001` 的所有清单文件路径/Hash 与 A05 原候选完全一致。Git 忽略图为 `artifacts/package-prep/windows11/tesseract-msys2-poc-delay-graph-a06.json`。

以固定合成中文 PNG 在该候选 `chi_sim+eng` 命令上实际运行，退出码 0；PowerShell `Start-Process -WindowStyle Hidden -PassThru` 后每约 20 ms 调用 `Get-Process -Id <pid> -Module`，12 次成功采样并去重：随包35/35 PE，另23个模块均在 `C:\Windows\System32`。这只证明**该运行样例的采样窗口**未看到额外非系统 DLL，既不能保证采样覆盖所有短时加载，也不能保证 PDF、TIFF、网络格式等未测路径。依据 [Microsoft 运行时动态链接说明](https://learn.microsoft.com/en-us/windows/win32/dlls/run-time-dynamic-linking)，`LoadLibrary`/`LoadLibraryEx` 不一定在 PE 导入目录呈现；故不将本项判作动态依赖完整证明。

定向单元测试8项 PASS（含延迟导入本地递归、坏属性拒绝、A05 构建器及 A06-P01 许可证据回归），脚本语法校验 PASS。结果为 `STATIC_DELAY_IMPORTS_ZERO + ONE_RUNTIME_SAMPLE_35_OF_35`，`release_eligible=false`。更强的运行期 LoadImage 跟踪、其他输入类型、签名、许可证义务、真实质量与 Server2025/目标账户验收仍待。
