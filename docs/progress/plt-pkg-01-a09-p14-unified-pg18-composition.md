# PLT-PKG-01-A09-P14：统一候选与PG旁包只读组合计划

日期：2026-10-01；状态：`NON_RELEASE_INPUTS_DISJOINT_AND_VERIFIED / COMBINED_ZIP_NOT_BUILT`。机读报告见 [组合计划](plt-pkg-01-a09-p14-unified-pg18-composition.json)，SHA-256 `6741b716c886f9128bf6c2bca6a60ff2f83ae3c07eefa82d521d6ee2348761ef`。

编码前检查：Phase 2/Gate 3 开放；输入限定为P10含OCR许可文本的统一非发行ZIP和P12 PG18/pgvector非发行旁包，两者均已各自完整性验证，P13仅证明PG最小合成功能。本项只读核固定ZIP与内部清单，不改业务/API/Schema/Migration、正式服务/数据库或旧ZIP。验收：每个来源的整体SHA、kind/非发行声明、载荷清单与全部文件字节、大小写折叠路径冲突及PG目标前缀；失败拒绝计划。回滚撤新审计工具/报告，原包原样保留。

结果：统一候选19,474件（SHA-256 `e4fdbcb601f526fd147b73b3e510e82653d85841503b5589dbf5c5d7c2f2eb50`）、PG旁包1,629件（SHA-256 `d0e038b43240369f7cd66396c34cd8e56d5a7a5a51ae3bc6f5fc41783baa7fd9`）均逐件核对；合计21,103件，大小写不敏感路径冲突0。PG文件只映射 `payload/pgsql/` 与 `payload/third-party-licenses/`，统一候选原无 `payload/pgsql/`。定向单元2/2。未生成合并ZIP，未安装、启动或迁移数据库。

计划下项在不覆盖历史候选前提下复制两包精确载荷，重建顶层 manifest/hash/双来源许可清单，ZIP回读及ASCII清洁解包，并保持 `release_eligible=false`。产品许可/签名、Ghostscript及所有第三方义务/对应源码、正式服务账户/ACL/HTTPS、Server2025产品包验收、Debian13和Gate仍开放。
