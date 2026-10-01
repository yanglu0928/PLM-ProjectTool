# PLT-PKG-01-A08-P09-P05-P03-A07-P03-P01：无 JBIG 候选许可义务分流

日期：2026-10-01；状态：`EVIDENCE_INVENTORY_PASS / LICENSE_RELEASE_BLOCKED`。输入是 A06 已提交的 [35 项许可定位表](plt-pkg-01-a08-p09-p05-p03-a06-msys2-license-evidence.csv)、CR-PKG-004 和 A07-P02 两次源码构建结果。仅审计/记录，不修改产品许可、正式安装资产或 Gate 判定。旧表仍代表旧 35 PE 候选，不追写；新候选以删除 `libjbig-0.dll`、将 `libtiff-6.dll` 置换为源码构建版本形成 34 PE 清单。

## 可核事实

- 34 个本地 PE 中，33 项继承 A06 的包/许可文本定位证据；旧 `libtiff-6.dll` 的二进制与许可行**不得**冒认为新 DLL 的精确来源。新 DLL 来源是固定 libtiff4.7.2 上游 tar SHA-256 `672bd7d10aee4606171afb864f3570b83340f6a33e2c186dc0512f7145ffdf6a`，源码 `LICENSE.md` SHA-256 `0e27c2382d7b8147972bbb746e04059a1152c8d0fda9d03ef1399d1a433c4ade`；构建脚本、工具链、选项及两个输出 Hash 见 A07-P02。此处只确认许可原文位置/Hash，不推定其覆盖所有静态/动态合并代码。
- 旧候选中唯一 `libjbig-0.dll` 行已从新静态闭包删除；`libtiff-6.dll` 新普通导入不再有 JBIG。此项降低特定 GPL-2.0 直接依赖风险，但不证明整个产品与 Apache-2.0、AGPLv3 或 GPL 家族兼容。
- 其余 33 项中，有 13 个 PE 的包级声明含 Apache、GPL、LGPL 或“BSD | GPL”双许可/混合声明：`libgcc_s_seh-1.dll`、`libgomp-1.dll`、`libiconv-2.dll`、`libidn2-0.dll`、`libintl-8.dll`、`liblerc.dll`、`liblz4.dll`、`liblzma-5.dll`、`libstdc++-6.dll`、`libtesseract-5.5.dll`、`libunistring-5.dll`、`libzstd.dll`、`tesseract.exe`。其中包级元数据不等于每个 DLL 的最终适用条款；需核具体源文件、例外、可选许可及分发结构。其他 21 项的 MIT/BSD/custom/Zlib 等声明也须保留版权/许可文本，不是“无需审查”。
- [GNU LGPL FAQ](https://www.gnu.org/licenses/gpl-faq.en.html#LGPLStaticVsDynamic)说明一并分发 LGPL 库时，即使动态链接仍有库源码交付要求；[GCC Runtime Library Exception FAQ](https://www.gnu.org/licenses/gcc-exception-3.1-faq.en.html)明确例外不取消单独分发运行库本身的源码要求。这些是义务检查线索，不是对本组合的最终法律意见。
- 仓库根目录当前无 `LICENSE`/`NOTICE`；ADR-002 已将 GitHub 公开、兼容项目许可证、完整对应源码/构建安装资料与第三方声明列为 Ghostscript 对外发行前置。私人 GitHub 远端同步不等于公开或合规。本轮没有更改仓库可见性，也没有自行指定产品许可证。

## 发行前清单与未决

1. 对 34 个 PE 建立与最终二进制精确对应的源归档、实际适用许可、版权/NOTICE、源码交付方式；新 libtiff 包含构建配方差异，不能引用 MSYS2 官方包签名背书。与 Ghostscript、Python wheel、前端包、模型另行合并成完整产品清单。
2. 对 GPL/LGPL/例外/多许可证项逐个核条款与源文件，明确相互链接及分发结构；确认修改库替换/重链接路径、对应源码、版本更新与安全修复责任。请有资质人员复核最终发行条款和兼容性；在此之前保持 `release_eligible=false`。
3. JBIG TIFF 能力收缩须在升级前有可执行的识别、阻断或转换方案和回退测试；当前 `tiffcp` 负例通过，但 Tesseract CLI 负例不具区分力，不能靠 CLI 退出码安全拒绝。
4. 正式发行仍需公开仓库/项目许可证、Third Party Notices、源码和构建资料、签名信任、完整动态加载、Windows Server 2025 与目标账户、真实质量/性能、离线安装升级、Gate 3/UAT。Debian 13 验证按用户指令暂缓，仍保留目标环境。

【待确认】问题：最终项目许可证及有资质的组合许可复核结论尚未形成。影响：含 Ghostscript/Tesseract 的对外发行不能标记合规。当前可选方案：继续本地非发行开发与内部验证；发行前完成 AGPL 兼容项目许可证、精确源码/NOTICE 与许可复核；若不能满足，另行评估不含受限组件或商业路径。建议：先完成技术及证据包，最终法律/公开动作在客观条件具备后实施。是否阻塞：阻塞外发发行，不阻塞独立工程任务。
