# PLT-PKG-01-A09-P43-A03：含 Ghostscript 源码的新非发行候选

日期：2026-10-01；状态：`NON_RELEASE_GHOSTSCRIPT_SOURCE_CANDIDATE_INTEGRITY_PASS / LEGAL_CLEARANCE_OPEN`。实施前已登记 [CR-PKG-006](../changes/CR-PKG-006-ghostscript-source-candidate.md)。输入 P33 固定 ZIP SHA-256 `85424ce4f58f277355bfb69f89cd980fe18d1fd865ff2e5fe4b9483c9747b1cc`、P22 祖先、P43-A02 官方 Ghostscript 10.08.0 `.tar.xz` SHA-256 `c20492bc8ebb96c87fa2e52a0926e1cda8cde95d66145e018ac713fed5da38cf`。

编码前检查：Phase 2/Gate 3 开放；本项只新建非发行 ZIP，不更换 Ghostscript 二进制、不触碰正式安装根/SCM/已有数据库/License 信任源。涉及实体、API、权限、Migration 均为无。验收是原候选 21,112 项载荷逐项不变，只增官方源码归档及源包 LICENSE 两项，重建三份 metadata 并保持所有发行/法律门禁关闭；独立验证器重验新旧谱系。风险为源归档不完整、误覆盖历史包、metadata 误写可发行或源包许可文件遗漏。

新增构建器与独立验证器。新 ZIP 位于本机 Git 忽略的 `artifacts/package-prep/windows11/unified-ghostscript-source-candidate-ac3c14b88aca/NOT-FOR-RELEASE-windows11-unified-pg18-caddy-go-ghostscript-source.zip`，748,147,289 字节，SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`。原 21,112 项全量 Hash 保持不变；只增 `payload/third-party-sources/ghostscript/ghostscript-10.08.0.tar.xz` 及 `payload/third-party-licenses/ghostscript/source-LICENSE`，总载荷 21,114 项；后者从同一官方源码包读取，SHA-256 `8ce064f423b7c24a011b6ebf9431b8bf9861a5255e47c84bfb23fc526d030a8b`。构建器逐项流式复制/读回并重验输入；独立验证器对新包/P33/P22 完整谱系、增量集合和非发行 metadata 实测退出 0。构建单元 3/3、独立验证单元 3/3；P43-A02 源码单元 3/3。

该包**没有**正式产品 LICENSE/NOTICE，也未完成 Ghostscript 源归档第三方子组件、其他运行依赖及组合发行义务的合格法律复核。归档同版且 Hash 正确不等于 Windows 二进制可重现构建。未清洁解包或执行新布局运行测试，不把构建/验证结果扩大为安装 PASS。`release_eligible=false`、`legal_clearance=false`、`review_status=REVIEW_REQUIRED` 均保留。兼容性：运行载荷、业务/API/Schema/Migration 不变；目标 Windows Server 2025 和 Debian 13 仍未验。升级：无迁移。回滚：停用新候选，原 P33/P22 ZIP 保留且 SHA 不变。

下一项 P43-A04：对新 ZIP 做清洁解包、完整落盘 Hash/源包回读与布局兼容性检查；随后继续产品级 NOTICE 和第三方义务收敛，不能提前关闭发行 Gate。
