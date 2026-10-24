# PLT-PKG-01-A09-P10：包含新增13项许可文本的统一非发行候选

日期：2026-10-01；状态：`INTERNAL_INTEGRITY_AND_SYNTHETIC_OCR_PASS / RELEASE_BLOCKED`。

编码前检查：Phase 2 / 本 WBS；输入为固定原统一候选SHA-256 `da285e1c88d45f195d141f5eb6cba5f887f019063f4547a0a54ecae78c251bff`及新增13项/25份许可文本旁包SHA-256 `a9a2ef6f295ac01d14561a64f6b0b5fe3f83d1535dc899b2893576ca0282e71e`。仅构造新的非发行ZIP并扩大清洁解包验证器的显式候选种类；不改产品业务、实体、API、权限、Migration、正式安装根或旧候选。验收：来源包/侧载全量Hash先验，原19,449件逐字节保留、新25件加入、重建清单并逐件回读，全新ASCII空目录解包复核、合成OCR回归。风险/回滚：新包仍不是安装器/法律批准；弃用Git忽略新包，旧ZIP/旁包保持不变。

新候选：`artifacts/package-prep/windows11/unified-noticed-candidate-08833f3eec28/NOT-FOR-RELEASE-windows11-unified-noticed-candidate.zip`，462,062,317字节，SHA-256 `e4fdbcb601f526fd147b73b3e510e82653d85841503b5589dbf5c5d7c2f2eb50`。载荷19,474件，含旧19,449件及新增25件；顶层另有3个清单。构建后ZIP内19,474件逐件Hash与清单一致；在全新ASCII Temp目录解包后，19,474/19,474逐件读盘Hash及完整文件集 `CLEAN_EXTRACT_HASH_PASS`。新增文本位于`payload/third-party-licenses/ocr-python-notices/`；旧统一候选未覆盖。

验证器默认仍只接受旧种类，只有显式`--expected-kind WINDOWS11_UNIFIED_NOTICED_DEVELOPMENT_CANDIDATE`才接受新种类，伪造发行标志仍拒绝。定向单测5/5通过（含同Hash不同路径的源文件保留、清洁解包错误种类拒绝）。新包ASCII解包目录的嵌入式Python+包内Tesseract/Ghostscript对合成表格PDF运行OCRmyPDF `--deskew --output-type pdfa-2 --tesseract-pagesegmode 3`，exit0、PDF/A-2b真、五术语5/5。未重复四版面全量质量测试，不能把旧候选四版面结果自动转写为新包全量质量PASS。

manifest继续固定`release_eligible=false`、`legal_clearance=false`、`corresponding_source_included=false`；仅完成25份文本并入，不代表独立源码/NOTICE总表、Ghostscript AGPL公开与法律复核、原生34项义务、PG18/pgvector离线安装、正式License/签名、Server2025/Debian13或Gate通过。ZIP为本机Git忽略非发行产物；代码/测试/版本记录同步GitHub。下一任务优先固定PostgreSQL18/pgvector的离线安装输入及目标平台来源，不对正式环境安装。`release_eligible=false`。
