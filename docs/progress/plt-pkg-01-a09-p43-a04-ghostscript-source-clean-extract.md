# PLT-PKG-01-A09-P43-A04：Ghostscript 源码候选清洁解包

日期：2026-10-01；状态：`NON_RELEASE_GHOSTSCRIPT_SOURCE_CLEAN_EXTRACT_PASS / FORMAL_RELEASE_BLOCKED`。输入为 P43-A03 非发行候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、固定 P33/P22 谱系和 CR-PKG-006。

编码前检查：Phase 2/Gate 3 开放；本任务只在新的 ASCII Temp 直属目录做解包和字节读回，不碰正式安装根、SCM、既有数据库、License 或客户资料。实体/API/权限/Migration 均无变动。验收是全文件集、全量 Hash、Ghostscript 源归档/源包 LICENSE 内外同字节、来源包末次复核；风险是超长 Windows 路径、解包遗漏、用构建器报告代替落盘验证。

`tools/stage_windows_unified_ghostscript_source_candidate.py` 在独立验证 P43-A03 ZIP 后，解包至本机 `C:\Users\17231\AppData\Local\Temp\plm-gs-source-stage-20261001a`。21,114 个载荷与三份 metadata 全部独立落盘，逐项 Hash 和文件全集回读通过；`verify_windows_unified_extract` 新增只允许本候选 kind 的非发行识别。随包 `ghostscript-10.08.0.tar.xz` SHA-256 `c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf`、源包 LICENSE SHA-256 `8ce064f423b7c24a011b6ebf9431b8bf9861a5255e47c84bfb23fc526d030a8b` 与归档内部内容一致，`doc/COPYING` SHA-256 与原随包文本一致；最后再验来源 ZIP 与父谱系未变。真实脚本退出 0，定向单元 2/2。

兼容性：只扩展非发行解包验证 kind，不改变业务运行载荷/API/Schema/SCM；Windows 11 Temp 隔离验证，Windows Server 2025 和 Debian 13 未验。升级：无迁移。回滚：弃用新暂存目录与验证工具，P33 原包仍在；暂存目录为 Git 外本地测试产物，不是正式安装。尚未测试新候选的目标布局、OCR/HTTPS 运行、产品 LICENSE/NOTICE、法律审核或目标平台，`release_eligible=false`。下一项 P43-A05 只核新包到隔离安装布局的映射/运行兼容，再处理法律及正式信任源门禁。
