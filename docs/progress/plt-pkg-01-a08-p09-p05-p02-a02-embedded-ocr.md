# PLT-PKG-01-A08-P09-P05-P02-A02：嵌入式 OCRmyPDF 非发行运行时

## 编码前检查

- Phase/WBS：Phase 2 / `PLT-PKG-01-A08-P09-P05-P02-A02`；仅将已校验的 106-wheel 联合闭包装入新的 Windows 非发行 Python 运行时并验证 OCR 命令。
- 输入/前置：官方 Python3.13.15 AMD64 embed ZIP 固定 SHA、后端93-wheel、CR-PKG-002 联合106-wheel及 P02-A01 全新无索引 `pip check`。正式 ACL 阻塞与原生组件许可缺项不作为此候选的 PASS 前提。
- 模块/实体/API/权限：仅扩展嵌入式构建脚本的可选联合 OCR 输入；省略该参数时旧93-wheel路径不变。不改后端依赖、Parser 配置、实体、API、权限、Schema 或 Migration。
- 验收：联合来源106项 Hash/旧后端93项完全相同；单次旁装避免重叠 `bin` 目录；私有 `sys.path`、无目标机 pip、106项发行元数据、清洁 PATH 导入及真实 PDF/A-2b/`--deskew` 命令。
- 风险/回滚：当前 OCR 系统组件仍从开发机/项目 PoC 路径显式提供，并未并入交付包；旧候选不覆盖，弃用新忽略目录即可回滚。真实质量/合法分发/目标账户与系统未获验收。

## Windows 11 实测

- 初版两次旁装虽导入与标准版面命令通过，但 pip 报 `packages/bin` 已存在；为避免覆盖歧义，改为对已校验的联合 wheelhouse **一次** `pip --no-index --target` 构建，并重新执行同一批核心检查。最终运行时为 Git 忽略的 `artifacts/package-prep/windows11/embedded-backend-20261001-033602-abc36560/runtime`。
- 官方 embed ZIP、93后端与106联合 wheel Hash 逐件通过；联合清单恰多13项，`charset_normalizer` 继续保持后端3.5.2。Python 私有 `sys.path`、`pip_present=false`、106/106 `.dist-info`、产品/Paddle/OCRmyPDF/pikepdf 原生导入及清洁 PATH 导入 PASS。省略新参数的旧入口重新构建 93/93 发行元数据/清洁 PATH PASS；原构建入口定向坏 ZIP/不完整 wheel 2/2 拒绝，新联合输入越界路径拒绝。
- 以该最终嵌入式解释器运行 POC-01 验证器；显式指定本机官方 Tesseract5.5.3 解包、Ghostscript10.08.0 portable 与 ASCII `tessdata_best`，对合成表格版面执行 OCRmyPDF17.12.1、`--tesseract-pagesegmode 3 --deskew --output-type pdfa-2`，进程 exit0，PDF/A-2b 验证 PASS，五个预期术语 5/5。另在初版双旁装解释器上完成标准版面 5/5，但以最终单次旁装结果为本项结论。无客户资料外发。

## 限制与下一项

新运行时不是完整离线发行包：Tesseract/Ghostscript/tessdata 仍是分离的开发机路径；没有只读 ACL/目标服务账户、完整许可/源码义务审查、安装/升级工具、Server2025/Debian13、真实独立质量或 Gate 3。`release_eligible=false`。下一项应把离线原生组件/模型以固定来源和许可材料装入**新的非发行**候选并在清洁目录验证，同时继续处理 CR-PKG-001 的签名与原生归属；不得覆盖旧包。
