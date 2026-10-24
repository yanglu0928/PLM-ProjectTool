# PLT-PKG-01-A09-P29：Caddy SBOM组件审查队列

日期：2026-10-01；状态：`NON_RELEASE_CADDY_SBOM_REVIEW_QUEUE / LEGAL_REVIEW_OPEN`。输入固定P22 ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`、CycloneDX 1.6 SBOM SHA-256 `ecc0c7270380760e6ab62521dcc6baee8a4e7324319bfdaf0874cd5ec74f7e88`及P28技术差异。

编码前检查：Phase2/Gate3开放，P28法律审查仍待；本项仅从固定官方SBOM生成可追溯待审核清单，无产品/包/API/Schema/服务变更。完整ZIP逐件Hash先验、SBOM Hash固定、149项`bom-ref`唯一性、行排序/输出Hash读回；不根据空许可字段自动推断无许可或已批准。

`tools/build_caddy_sbom_review_queue.py`输出[149项组件队列](plt-pkg-01-a09-p29-caddy-sbom-review-queue.csv)，SHA-256 `3b72ab936c13ff04aff00b2bfae2002c17a00430734943725efc2c5712aca232`。每行保留原`bom-ref`、名称、版本、PURL、SBOM许可字段及`REVIEW_REQUIRED`。149项中148项在**该SBOM**没有许可证字段、2项缺PURL、1项缺版本；这不等于实际许可不存在。定向单元2/2、固定包真实构建exit0。首次把缺版本组件判非法，未生成CSV；改为保留空值并统计后全程重跑通过。队列不含客户数据或Secret。

仍需针对149项核出处、许可文本/版权声明/相应源码及最终NOTICE适用性，并联同Ghostscript、Python、原生OCR、前端、PostgreSQL/pgvector和产品LICENSE做有资质法律复核；`legal_clearance=false`、`release_eligible=false`。下一项P30可按固定队列补充分家族/来源证据，不得把仅有Caddy官方SBOM当成下游完整声明。回滚撤队列与生成器即可，不改原始候选。
