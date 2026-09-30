# PLT-PKG-01-A08-P09-P05-P03-A04：Tesseract 静态子集 DLL 来源矩阵（首轮）

## 编码前检查与边界

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A04`。输入为已冻结的官方 Tesseract 5.5.3 安装资产解包及 A03 静态 PE 图；仅追溯该图的 33 个 DLL，不改变产品运行路径、安装、API、数据库或 License 机制。
- 验收口径：每个 DLL 先与官方解包逐字节 SHA-256 对账，再与官方历史 MSYS2 包内的同名 DLL 对账；包名、版本资源和软件包声明单独记录，不以同名/同版本推断字节来源或许可。只把精确匹配标为已定位候选，仍不代表完整发行合规。
- 风险/回滚：静态图不是动态依赖全集；上游资产未附精确构建时包锁；其余 DLL 和 Ghostscript/PyMuPDF 的权利链未解决。可撤新审计脚本/本地忽略候选包，原始旁包与冻结基线不变。

## 首轮结果（Windows 11，2026-10-01）

审计脚本 `tools/audit_tesseract_dll_provenance.ps1` 对静态图 33/33 DLL 复核官方解包 SHA；本地完整逐项机器报告为 Git 忽略文件 `artifacts/package-prep/windows11/tesseract-33-dll-provenance-a04.json`。结果：**2/33 找到官方历史包内精确二进制匹配，31/33 精确包来源与对应许可尚未定位**；`release_eligible=false`。

验证：PowerShell 语法解析 0 错误；33 行/2 精确匹配/31 阻断的机器结果断言通过；篡改冻结图中 `libcurl-4.dll` SHA 的反例按预期拒绝；`git diff --check` 通过。

| 文件 | 官方资产 DLL SHA-256 | 历史包与字节证据 | 许可文本证据 | 结论 |
|---|---|---|---|---|
| `libcurl-4.dll` | `3d302f9690e810fdfd950254e2f0663d0ff768737f350c602a4ed3a06e9b6b2b` | 官方 MSYS2 `mingw-w64-x86_64-curl-winssl-8.21.0-2-any.pkg.tar.zst` SHA `5bc07a331bd27e299dddbbd6c62d2edaba3da0c09a70ab30d8c71307d1156fd`；包内 DLL 与官方安装资产 SHA 完全一致 | 包内 `.PKGINFO` 为 `spdx:MIT`，`mingw64/share/licenses/curl/LICENSE` SHA `82f2f4427d6545ee5aaac4f0b80428da6cc8ba41c2cf5da3a03680ec327b9681` | `EXACT_BINARY_MATCH_LICENSE_TEXT_LOCATED`，仅此 DLL 的包/许可文本候选已定位；发行通知、其依赖及法律审查未关闭 |
| `libexpat-1.dll` | `92ae866c6c58dd2d8366aa0e6230ba8d434d5306e8d8c3a08b7e61750fc16153` | 官方 MSYS2 `mingw-w64-x86_64-expat-2.8.2-1-any.pkg.tar.zst` SHA `9f25550c738b7695164f4ea237af40512d7c63b4cd97aa417f3e0214930aca4f`；包内 DLL 与官方安装资产 SHA 完全一致 | 包内 `.PKGINFO` 为 `spdx:MIT`，`mingw64/share/licenses/expat/COPYING` SHA `31b15de82aa19a845156169a17a5488bf597e561b2c318d159ed583139b25e87` | `EXACT_BINARY_MATCH_LICENSE_TEXT_LOCATED`，仅此 DLL 的包/许可文本候选已定位；发行通知与法律审查未关闭 |
| 其余 31 DLL | 见本地逐项机器报告及既有 PE 图 | 未完成精确包内字节匹配 | 不从文件名或版本资源推断 | `EXACT_PACKAGE_AND_LICENSE_UNRESOLVED` |

排除对照：同目录历史 `curl-winssl-8.21.0-1` 包 SHA `741a92c1abeb05f3478389301a6440fb6edac8b99f2c21cbb1cabfadb5a4421a` 的 `libcurl-4.dll` SHA 为 `5a3c44d9d710802523220174e356161e8011e1d2d8ff29ec630be399b590760f`，**不等于**官方安装资产。两者均报告 `8.21.0` 文件版本，证明版本资源不足以确定包修订。候选包来自 [MSYS2 官方包归档](https://repo.msys2.org/mingw/mingw64/)；固定候选文件 URL：[`8.21.0-2`](https://repo.msys2.org/mingw/mingw64/mingw-w64-x86_64-curl-winssl-8.21.0-2-any.pkg.tar.zst)、[`8.21.0-1`](https://repo.msys2.org/mingw/mingw64/mingw-w64-x86_64-curl-winssl-8.21.0-1-any.pkg.tar.zst)。

Expat 固定候选文件来自同一[官方归档](https://repo.msys2.org/mingw/mingw64/mingw-w64-x86_64-expat-2.8.2-1-any.pkg.tar.zst)。

后续继续定位其余 31 个 DLL 的精确历史包、包内许可证与归档哈希，并检查完整动态加载路径、发行通知及 AGPL/产品许可。没有这些证据前，不将静态子集并入可交付发行包，也不关闭 Gate 3。
