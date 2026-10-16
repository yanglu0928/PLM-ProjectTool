# PLT-PKG-01-A08-P09-P05-P01：OCRmyPDF Windows 离线 wheel 闭包

## 编码前检查

- 当前 Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P01`。正式模型 ACL 子项因缺管理员/独立服务账户客观阻塞；本项为独立的 Python 离线依赖准备。
- 输入基线：POC-01 Windows 11 的 109-wheel `wheelhouse-sha256sums.txt`，固定 `ocrmypdf==17.12.1` 主 wheel SHA-256 `d1fc83dd2b567011f10afdd7612576f13c40183cbf1d867f898b64bb62d5f515`；现有后端 93-wheel 非发行候选不含 OCRmyPDF。
- 模块/实体/API/权限：仅新增本地无索引依赖闭包构建工具；不改生产依赖、Parser 配置、实体、API、权限、Schema 或 Migration。
- 验收：Python 3.13 x64 身份；109/109 来源 Hash；`--no-index --only-binary` 完整解析；选中轮子再验 Hash；全新 venv `--no-index` 安装、`pip check` 与 OCRmyPDF/pikepdf 导入。
- 风险/回滚：PyPI wheel 闭包不等于系统 Tesseract/Ghostscript、完整发行许可/物理断网或目标环境。旧候选不覆盖；可撤工具和 Git 忽略的本地输出。

## Windows 11 实测

- 使用 `py -3.13` 的 Python 3.13.15 AMD64，109/109 PoC wheel 与历史清单逐项匹配；`pip download --no-index --only-binary=:all:` 从本地选取 26 wheel，总计 38,696,937 字节。输出在 Git 忽略的 `artifacts/package-prep/windows11/ocrmypdf-20261001-032140-5522f0f8`，每件轮子重核原清单，`sha256sums.txt` 文件 SHA-256 为 `9628605e7402dd59a6c4020fbfb0c228aa89618b96e2050594e4505bc7a9917d`。
- 全新 venv 从这 26 wheel 无索引安装 `ocrmypdf==17.12.1`，`pip check` 无损坏依赖，OCRmyPDF 与 pikepdf 导入 PASS。非 3.13 解释器、错误格式来源清单均在创建输出前拒绝。
- 与 A06 现有嵌入式运行时的 93 个发行元数据仅作名称对照，选中闭包有 13 个尚缺：`defusedxml`、`fonttools`、`fpdf2`、`img2pdf`、`markdown_it_py`、`mdurl`、`ocrmypdf`、`pdfminer_six`、`pikepdf`、`pluggy`、`pygments`、`rich`、`uharfbuzz`。本项未验证重叠包的版本或原生文件映射兼容，因此不称并包完成。

## 下一项与发行边界

下一子项以固定 wheel 和旧候选为输入，构造新的**非发行**嵌入式 Python 候选并清洁导入/真实 OCRmyPDF 命令复验；仍须保持旧包不变。Tesseract 5.5.3 Authenticode/原生 DLL 与 JAR 精确来源和许可、Ghostscript/PyMuPDF AGPL 分发、正式 ACL/服务账户、独立真实质量、Server 2025/Debian 13 与 Gate 3 均未通过，`release_eligible=false`。
