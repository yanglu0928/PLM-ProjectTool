# PLT-PKG-01-A08-P09-P05-P03-A07-P01：Tesseract 候选许可风险分流

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P03-A07-P01`；仅分析 A06 证据矩阵与包内许可声明/直接链接关系，记录下一步技术控制，不作法律 PASS。
- 输入基线/前置：CR-PKG-003、35 行精确二进制来源与文本证据、A06 PE 图；Gate 2 已通过，Release Gate 未通过。
- 模块/实体/API/权限：CR-PKG-004 与风险登记；无产品代码、ORM/Migration、API、权限、安装包或公开仓库状态变化。
- 验收：准确区分包声明、文件级适用和完整分发义务；识别高风险链接边及可验证替代；保持发行阻断。
- 风险/回滚：许可证解释取决于实际文件、链接与交付方式；本文不是法律意见。可撤风险建议但不能抹除已发现的包/PE 事实，原候选不变。

## 分流结果（2026-10-01）

固定 MSYS2 候选的 `libtiff-6.dll` 直接导入 `libjbig-0.dll`；后者固定包 `jbigkit 2.1-5` 声明 GPL-2.0 且包内有 GPL v2 正文。上游 [JBIG-KIT](https://www.cl.cam.ac.uk/~mgk25/jbigkit/)亦明确 GPL/另有商业授权。Tesseract 包声明 Apache-2.0；[Apache](https://apache.org/licenses/GPL-compatibility.html)与 [GNU](https://www.gnu.org/licenses/license-compatibility.en.html)官方许可说明提示 Apache-2.0 与 GPLv2 的兼容风险。这里不裁定该实际 DLL 链接结构的法律性质，但足以使完整候选发行条件继续失败。已先建立 [CR-PKG-004](../changes/CR-PKG-004-remove-jbig-from-windows-tesseract-candidate.md)，选择仅在隔离 PoC 中评估同版 libtiff 关闭 JBIG 支持；没有购买商业授权或将现有包发布。

另需逐文件审查：GCC 三个运行库的 Runtime Library Exception 是否适用及独立 DLL 源码提供方式，[GNU 官方 FAQ](https://www.gnu.org/licenses/gcc-exception-3.1-faq.html)说明例外不等于分发 DLL 时免除其自身 GPL 条款；`libintl`、`libiconv`、`libidn2`、`libunistring`、`liblzma` 等包有 GPL/LGPL/多许可声明，必须核适用文件、对应源码、用户替换/再链接与通知条件。`liblz4`、`libzstd` 等混合声明需要确定具体库许可分支；自定义声明也要核正文。A06 的 35 行只标文本位置、`release_obligations_reviewed=NO`，不能当 Third Party Notices 完稿。

结果：`LICENSE_RISK_IDENTIFIED / RELEASE_NOT_CLEARED`。下一项按 CR-PKG-004 先验证精确 libtiff 源码与 `--disable-jbig` 构建可行性；如果工具链/精确源码不可得，记录客观阻塞并转入不依赖该候选的发行工作。Ghostscript AGPL、全产品公开源码及其他组件的义务另有 Release Gate，不因本项自动通过。
