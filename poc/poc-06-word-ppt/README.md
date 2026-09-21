# POC-06 Word / PowerPoint 交付级样例

## Status

`IN_PROGRESS / WINDOWS11_PASS / SERVER_OFFICE_BLOCKED`

## Objective

验证 100 页 Word 与 50 页 PowerPoint 能否以纯合成中文内容稳定生成，覆盖多级章节、表格、图片和流程，并由 Microsoft Office 正常打开且无损坏。

本目录只包含 Phase 0 验证脚手架、合成输入和脱敏结果，不是正式交付模板或已冻结的输出服务实现。

## Environment

- Windows 11 Home 10.0.26200，x86-64。
- Microsoft Office Home and Student 2021，Word / PowerPoint 16.0.20326.20144。
- DOCX 生成：Python 3.13 + python-docx。
- PPTX 验证样例：Codex 工作区 Artifact Tool；正式产品技术基线仍保持 `python-pptx`，本 PoC 不据此修改技术栈。
- Windows Server 2025 Datacenter 10.0.26100：OOXML 包和 Hash 实机复验通过，但虚拟机未安装 Microsoft Word / PowerPoint，Office 实开验收被环境阻塞。
- Debian 13：尚未执行，不外推兼容性。

## Input

- `input/plm-collaboration.png`：无品牌、无客户信息的合成工业研发协同插图。
- 文本、表格和流程内容由脚本确定性生成，不读取方案库、合同、调研记录或标准能力库。

## Steps

1. 生成恰好 100 页的 DOCX，每页使用显式分页，包含三级标题、中文正文、表格、图片和流程。
2. 生成恰好 50 页的 PPTX，包含章节结构、原生表格、原生流程、可编辑数据图和单页图片。
3. 执行 OOXML 包完整性、页/幻灯片数量和覆盖项断言。
4. 使用 Microsoft Word 与 PowerPoint 以只读方式打开并导出 PDF，记录页数和对象统计。
5. 将 DOCX 与 PPTX 全量渲染为 PNG，逐页进行视觉检查。

## Result

Windows 11 全部验收通过。Microsoft Word 只读实开后计算为 100 页，PowerPoint 实开后计算为 50 页，两者均成功导出 PDF，未出现修复提示。OOXML 完整性、内容覆盖和 150 页全量视觉检查通过。

Windows Server 2025 实机复验两个文件的 SHA-256 与 Windows 11 一致；DOCX 包含 99 个显式分页、9 个表格和 4 个内联图形，PPTX 包含 50 张幻灯片。由于虚拟机未安装 Office，Server 子项仅为 `PARTIAL_PASS_OFFICE_BLOCKED`。

## Metrics

- DOCX：1,862,035 字节，SHA-256 `c02c542e360ac23d6ac9c7356b0e2d5f63906287b91883675d15a670f1faf2af`，100 页，99 个显式分页，9 个表格，4 个图片实例。
- PPTX：1,974,007 字节，SHA-256 `a5dacab4af80f8cf40cb773b17f8eda61fa5d27bde11d3bde92e6307dcf1397e`，50 页，1 个原生表格，3 条原生连接线，1 个图片实例。
- 视觉检查：Word 100/100；PowerPoint Office 导出 50/50；Artifact Tool 渲染 50/50；裁切、重叠、缺字问题 0。

## Logs

- 脱敏证据将保存到 `evidence/windows-11/`。
- Windows Server 2025 部分证据保存到 `evidence/windows-server-2025/`。
- 渲染页、Office 导出 PDF 和中间日志保存在 Git 忽略的 `artifacts/poc-06/`。

## Known Issues

1. Windows Server 2025 未安装 Microsoft Office，实开与 PDF 导出未验证；Debian 13 尚未执行。不得从 Windows 11 外推这两个平台的 Office 兼容性。
2. PPTX 样例使用工作区 Artifact Tool 生成，以满足当前制品制作规范；这不替换正式产品的 `python-pptx` 基线。
3. 工作区 DOCX 渲染器依赖 LibreOffice，当前未安装 `soffice.exe`；本轮改用目标应用 Microsoft Word 导出 PDF 并完成 100 页视觉检查。

## Conclusion

Windows 11 上从确定性生成、OOXML 完整性、Microsoft Office 实开到全量视觉检查的技术路径可行。Windows Server 2025 已证明相同制品的包结构和 Hash 不变，但因缺少 Office 不具备完整验收条件。

## PASS / FAIL

`IN_PROGRESS`：Windows 11 `PASS`；Windows Server 2025 `PARTIAL_PASS_OFFICE_BLOCKED`；Debian 13 `NOT_RUN`。

## Alternative

- 若复杂 DOCX 在渲染器间出现分页漂移，保留 Office 实开页数为主证据，并登记 LibreOffice 差异。
- 若 PPTX 中原生表格、数据图或流程在 Office 中损坏，保留失败文件与布局报告，不改成截图规避验收。
