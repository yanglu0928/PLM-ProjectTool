# PLT-PKG-01-A08-P09-P03-P03-P03-P01：Tesseract 上游构建来源族核查

## 编码前检查

- Phase/WBS：Phase 2 / PLT-PKG-01-A08-P09-P03-P03-P03-P01；只确认官方构建配方及可证明的来源族，不把名称关联当精确版本/许可验收。
- 输入基线/前置：CR-PKG-001、官方 5.5.3 Release 固定资产与 P03-P03-P02 的 139 文件/61 DLL/4 JAR SHA-256 清单。
- 模块/实体/API/权限：发行来源审计文档；无程序、业务实体、API、权限、Schema/Migration 变化。
- 验收：读取官方固定 tag 的构建脚本及递归依赖脚本，记录 Git blob 身份、直接包清单、DLL 归属的可证/推断边界与剩余来源缺口。
- 风险/回滚：构建配方不等于该发布资产的可复现构建证明，当前 MSYS2 页面版本可能不同于 2026-07 构建版本；撤此来源族记录即可回滚，不改二进制。

## 上游配方证据

官方 [5.5.3 `nsis/build.sh`](https://github.com/tesseract-ocr/tesseract/blob/5.5.3/nsis/build.sh) Git blob `0060aaf7e8c2725bc869b0b9b534e92998f75e54`，直接安装 12 个 MSYS2 mingw64 包：`curl-winssl`、`giflib`、`icu`、`leptonica`、`libarchive`、`libidn2`、`openjpeg2`、`openssl`、`pango`、`libpng`、`libtiff`、`libwebp`。它运行 [固定 tag 的 `nsis/find_deps.py`](https://github.com/tesseract-ocr/tesseract/blob/5.5.3/nsis/find_deps.py)（Git blob `0aa12a91b721d9165ea433fc36416bc95875a8d1`），从 `.exe/.dll` 导入表递归查找 `/mingw64/bin` 中的 DLL；另外显式加入 MinGW GCC 的 `libstdc++-6.dll` 与 `libgcc_s_seh-1.dll`，并执行 `make install-jars`。因此不能仅按 12 个直接包或顶层 `doc/LICENSE` 解释全部 61 DLL/4 JAR。

在当前解包清单中，21 个 DLL 文件名与 Tesseract 本体、上述直接依赖族或显式 GCC 运行时相符；这只是**名称/配方对应**，未核对应 MSYS2 精确 `.pkg.tar.zst` 的字节和版本。余下 40 个 DLL 包含递归传递依赖及 NSIS 插件，现阶段缺精确包归属/版本。4 个 JAR 的精确上游及许可仍未全部确认。当前 [MSYS2 包页面](https://packages.msys2.org/packages/mingw-w64-x86_64-curl)同时展示当前版本、许可证和文件清单，但其当前版本不能自动套用到 2026-07 的构建资产。

结果：`BUILD_RECIPE_FAMILY_IDENTIFIED / EXACT_BINARY_AND_LICENSE_ATTRIBUTION_INCOMPLETE`。下一项须取得 2026-07 构建包版本/Hash 或可复现构建证据，对 61 DLL/4 JAR 逐项匹配上游材料与许可原文/NOTICE；未完成前不把包内 Apache 文本当完整第三方许可，`release_eligible=false`。签名异常、OCR 独立质量、正式 ACL/Server2025 仍待。
