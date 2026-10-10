# PLT-PKG-01-A08-P01：Python wheel 许可证据对账

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行准备。
- 当前 WBS：PLT-PKG-01-A08-P01；A08 的 Python wheel 原始证据子项。
- 输入基线：A01 93 wheel/固定 SHA-256、A07 `release_eligible=false` 候选 ZIP、V2.1 Third Party License/离线发行要求。
- 前置任务：A01/A07 本机校验通过；Gate 3 和 Release 未通过，本项不得签发。
- 涉及模块：本地审计工具与发行证据；无业务实体、API、权限、Schema、Migration。
- 验收标准：93 个候选发行身份与原 wheel 一一对应，全部原 wheel Hash 复核，记录元数据与许可/通知文件 Hash；缺项、范围和发行阻塞明确。
- 风险：元数据/文件存在不等于法律合规；脚本不下载或上传客户资料、不修改既有候选；回滚可撤独立工具和本地忽略证据文件。

## 执行与证据

- `py -3.13 -m unittest tools.tests.test_audit_windows_candidate_licenses`：5/5 PASS，覆盖精确对账、Hash 篡改、身份不符、伪发行状态拒绝及许可证文件识别。
- `tools/audit_windows_candidate_licenses.py` 对 A07 ZIP 和 A01 wheelhouse：93/93 原 wheel SHA-256 一致，候选包名称/版本与原 wheel 93/93 一一对应；结果存于 Git 忽略的 `artifacts/package-prep/windows11/embedded-candidate-c81aa7bff37a/python-wheel-license-evidence.json`。工具只记录文件 Hash，不把许可证正文或二进制上传 Git。
- 原 wheel 的 91/93 含可识别许可/通知文件；无文件的两项是 `bce-python-sdk 0.9.79` 和自有 `plm-project-tool-backend 0.1.0.dev0`。前者原 wheel SHA-256 为 `71799ac8740505e0759d30873f6f1a478fa8f83aedf425d511f1419a5f30082e`，元数据 `License: Apache License 2.0`；[上游仓库](https://github.com/baidubce/bce-sdk-python) 主分支有 [Apache 2.0 许可证](https://github.com/baidubce/bce-sdk-python/blob/master/LICENSE)，但尚未证明该文本与 0.9.79 精确发行产物对应，也未补入候选 ZIP。
- `pypdfium2 5.13.0` 原 wheel 的 `.dist-info/licenses/` 包含平台 PDFium 及依赖许可材料；[上游 Licensing 说明](https://github.com/pypdfium2-team/pypdfium2#licensing)明确要求随二进制分发相关许可。脚本已按许可证目录而非仅文件名识别，并保留每个文件 Hash；内容/义务尚未逐项审查。
- A07 已安装目录清单此前仅 89/93 有识别文件；本次从原 wheel 识别 91/93。差额为 `et_xmlfile`、`openpyxl` 原 wheel 有许可文件、旁装目录未保留。交付载荷必须补齐并复核，不能用原 wheel 有文件代替 ZIP 已含文件。
- 自有 wheel 没有产品许可声明/文本。用户计划公开源代码，但尚无明确许可协议；不得替用户推定开源协议或对外授予权利。该项在正式开源/交付前保持待定。

## 结论与下一项

- 本子项为 `SOURCE_WHEEL_EVIDENCE_PASS / LICENSE_REVIEW_REQUIRED / RELEASE_BLOCKED`；它是 Python wheel 来源/文件证据，不是完整 SBOM、法律意见或可发行许可结论。前端、Python/PDFium 原生依赖、Ghostscript/OCR 系统组件、模型、插件及安装器未纳入本次审计。
- `PLT-PKG-01-A08-P02`：补齐候选载荷遗漏的 wheel 许可文件并复核 93 项 notice 覆盖；对 `bce-python-sdk` 查精确版本原始发布源，继续前端/原生组件清单。正式产品许可及发行合规保持阻塞，A07 ZIP 保留不覆盖。
