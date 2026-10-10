# PLT-PKG-01-A08-P09-P05-P03-A07-P02：无 JBIG libtiff 隔离构建

日期：2026-10-01；状态：`ISOLATED_POC_PASS / RELEASE_OPEN`；变更：CR-PKG-004。编码前检查：Gate 2 已冻结，Phase 2 进行中；本任务只增加非发行构建/审计工具，不修改 Parser 正式运行路径、API、ORM、Migration、安装资产或许可证。源输入与旧候选保留，已有未提交用户文件未覆盖。

## 固定输入及构建

- 官方 MSYS2 `mingw-w64-libtiff-4.7.2-1.src.tar.zst` SHA-256 `11f3bdc23a154a5cea2f8fffeab3e2a118bd773d2769e1dcea926ff02f2cf3e2`；其中上游 `tiff-4.7.2.tar.gz` SHA-256 `672bd7d10aee4606171afb864f3570b83340f6a33e2c186dc0512f7145ffdf6a`、PKGBUILD SHA-256 `2eecac8b6120c97e3b2754098f57c9bd026dcc121f67a9e2f9bf7e1a689e9819`、MSYS2 头文件安装补丁 SHA-256 `493742947c8667655b6b89f2d7d27e92e1438a490ed86f50811112394b432a12`。PKGBUILD 原静态/共享构建两处均启用 JBIG；本 PoC 未应用仅涉及头文件安装的 MSYS2 补丁，也不冒称官方 MSYS2 包的构建或签名。
- 临时 ASCII 路径中使用 2026-09-27 MSYS2 base，GCC 16.2.0-4、固定上游源码，配置 `--disable-static --enable-shared --enable-cxx --disable-jbig --enable-lerc --enable-libdeflate --enable-webp`，`CFLAGS/CXXFLAGS=-O2 -fno-strict-aliasing`；执行 `make -j4`、`make check -j4`。base 归档 SHA-256 `8a2095647afbf799d113d0cae35f7544589d059819042635504e75bd2179bd02`；签名文件虽已下载，未独立核验签名/信任链。包管理器更新后的完整工具链锁定与供应链证明尚未完成。
- `tools/build_libtiff_no_jbig_poc.ps1` 对固定源码/配方 Hash、源路径及旧 DLL 导出集合前置核查，拒绝覆盖输出；验证新 DLL 无 JBIG 导入与 libtiff 105/105 测试，并将输出标记 `release_eligible=false`。现有输出目录和篡改源码的负例均在创建输出前拒绝。

## 结果及边界

- 首次 DLL SHA-256 `3a8255fa962a84412954dc811452cb7dfe7e0b5aea6297931d4cdd0b665d72b0`，第二次独立构建 `3d1056450dc88b8b23915aef58196e898a1fca3e37e03543f08387fd5a6c3cd6`。两次 `make check` 均 105/105 PASS；与旧 MSYS2 DLL 的 412 个导出名集合相同。普通 PE 导入去掉 `libjbig-0.dll`，未增加其他导入；静态闭包从 35 减为 34 个本地 PE，未见未解析新依赖或延迟导入。
- 原始 DLL 并非逐字节相同。`tools/audit_pe_rebuild_equivalence.py` 只屏蔽 COFF 时间戳、PE 校验和与导出时间戳后，两次规范化 SHA-256 同为 `aed362450f70fa7b854385ee32b043773bf74d3319f3aae24bae3892a615b6b0`；审计工具正反例单元测试 2/2 PASS。此证据不等于完整可复现工具链或发行级二进制证明。
- 第一份新 DLL 放入独立 Tesseract 候选目录后，Windows 11 本机 `tesseract --version` 为 5.5.3；标准、密集、表格、倾斜四种合成 PDF 用 OCRmyPDF 17.12.1 `--deskew --output-type pdfa-2` 退出 0，PDF/A 检查和 20/20 术语通过。不是客户文档真实质量验收。
- 用 `tiffcp -c jbig` 构造 ISO JBIG 压缩 TIFF。旧 libtiff 的 `tiffcp -c none` 解码退出 0；新编译 `tiffcp` 退出 1 并显示未配置 ISO JBIG，证实格式能力收缩。旧/新 Tesseract CLI 均退出 0 但输出读图失败日志，因此该 CLI 负例不具区分力，不能声称应用层 JBIG 格式拒绝策略已验证。

## 下一步及回滚

本任务只可撤销新脚本并弃用 Git 忽略的临时构建/候选目录，旧候选与正式安装不变。CR-PKG-004 仍须解决 JBIG TIFF 升级识别/阻断或转换、完整动态装载、其他 GPL/LGPL/AGPL 与源代码/NOTICE 义务、签名/供应链、正式目标账户及 Server 2025、真实质量/性能、离线安装/升级后才能评估发行。Debian 13 当前按用户要求暂缓验证，但保留正式目标，不虚报通过。
