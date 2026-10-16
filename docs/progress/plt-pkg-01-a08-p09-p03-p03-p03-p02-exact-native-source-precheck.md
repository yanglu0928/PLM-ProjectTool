# PLT-PKG-01-A08-P09-P03-P03-P03-P02：原生依赖精确来源前置核查

- 上游 Tesseract 官方 5.5.3 Release API 显示 Windows 安装资产创建于 2026-07-24 20:14 UTC，大小与 digest 已在 P03-P01 固定。官方固定构建脚本使用 `pacman -Syu` / `pacman -S`，不锁包版本；现时 [MSYS2 包目录](https://packages.msys2.org/packages/mingw-w64-x86_64-curl)展示的是随时间变化的当前版本，不能代表 2026-07 的二进制。
- 本机查询官方 Windows installer 工作流公开运行清单，邻近记录为 2026-06-30 与 2026-07-30，未找到与 7 月 24 日发布资产直接对应的公开运行；不能断定资产未由该脚本构建，也不能从其他日期日志推定精确版本。
- 因缺构建时包锁/可复现构建清单，61 DLL/4 JAR 的**逐字节上游包归属和精确许可文本**未完成。本任务保持 `SOURCE_PROVENANCE_PRECONDITION_BLOCKED`，不标 PASS；P03-P03-P03-P01 的 21 个名称/来源族映射仅供排查。
- 后续可从上游发布者获取当次构建 SBOM/包清单，或对候选时期 MSYS2 包逐个取 SHA 对账；完成之前不并入正式发行包。此项不阻塞独立 OCR 质量和受控模型安装验证；`release_eligible=false`。
