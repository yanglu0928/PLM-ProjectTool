# PLT-PKG-01-A09-P28：新候选发行证据差异复核

日期：2026-10-01；状态：`NON_RELEASE_EVIDENCE_GAPS_RECONCILED / LEGAL_CLEARANCE_OPEN`。基于P22固定ZIP SHA-256 `2ac746411ff68cfd3f9fa08a2483ca3473c2c83d3d65531f5e8d21f40a6ac6a5`、P08早期许可差异及`CR-PKG-005`。本项是技术文件/元数据盘点，不解释或批准法律义务。

编码前检查：Phase2/Gate3开放，P27已确认正式License信任源缺失；本项独立盘点，无业务/API/Schema/数据/SCM修改。先独立验证21,110项固定ZIP逐件Hash，再核重要许可/源码文件与嵌套`REVIEW_REQUIRED`状态，不因文本存在宣布发行PASS。若候选文件或审核状态变更，拒绝沿用本报告。

`tools/audit_caddy_candidate_release_evidence.py`真实固定包审计exit0、定向单元2/2。OCR Python新增13项的独立许可文本25份在包内；`payload/third-party-sources/`仅1份Caddy buildable artifact。包内有Caddy LICENSE/SBOM/checksums及PG/pgvector许可文件、Ghostscript `doc/COPYING`；产品级顶层`LICENSE`/`NOTICE`为0，Ghostscript对应源码未在本候选中定位。Caddy下游NOTICE、PG/pgvector、前端依赖审核标志均保持未完成；P08的34项Tesseract PE义务未审，不能用Caddy源码1份覆盖其他家族。所有重要文件Hash由审计脚本输出，报告明确`legal_clearance=false`、`release_eligible=false`。

下一项P29可从固定Caddy SBOM/已打包许可文本继续生成组件级审查队列与所需出处，其他家族逐项补齐对应源码/声明；正式产品LICENSE/NOTICE与Ghostscript AGPL适用路径需有资质人员审核，AI不能代替法律批准。正式信任源、安装器、三平台、质量和Gate仍开放。回滚仅弃用本只读报告/工具，候选ZIP历史不变。
