# 原生 OCR 组件的发行许可材料映射

日期：2026-10-01；任务：PLT-PKG-01-A09-P45-A01。本文供发行负责人和合格法律审阅人员核查 Windows 11 固定非发行候选中的 34 个原生 PE。主要结论是：二进制身份已逐项核对，但候选内没有按原生组件归属的许可通知侧载，不能据此发行。

输入 P43 候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P33/P22 谱系及[既有原生 PE 来源矩阵](plt-pkg-01-a08-p09-p05-p03-a07-p03-no-jbig-license-evidence.csv) SHA-256 `a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc`。编码前检查：Phase 2、Gate 3 未关闭；只读核对包内二进制和矩阵许可证据，不改发行包、业务实体、API、权限、Schema、Migration、SCM 或生产安装。风险是将本机来源矩阵或相同的通用许可正文误当成候选内已为对应 DLL 建立的归属通知。

[只读审计工具](../../tools/audit_native_pe_license_materials.py)先重验候选谱系与矩阵身份，再逐个检查 34 个 `payload/ocr/tesseract/` 中 PE 的 SHA-256 与矩阵一致。矩阵列有 61 条许可文本证据记录（共享来源会重复），其中 30 个 PE 的状态为 `PACKAGE_TEXT_HASH_VERIFIED`、3 个为 `PRIOR_A04_SOURCE_TEXT_REFERENCE`、1 个为 `SOURCE_TEXT_HASH_VERIFIED`。对候选中名称含 LICENSE/LICENCE/COPYING/NOTICE 的 327 条路径做正文 SHA-256 比对，61 条中仅 3 条在其他 Python 组件材料里发现相同文本；这不是原生组件专属侧载或归属证明。候选 `payload/third-party-licenses/native-ocr/` 专属通知路径为 0，矩阵 34 项 `release_obligations_reviewed` 均仍为 `NO`。[34 行逐项映射](plt-pkg-01-a09-p45-a01-native-pe-review-inputs.csv)保留二进制、精确来源、声明和矩阵证据路径/哈希。

真实固定候选审计退出 0，定向单元 4/4。审计成功只表示“现有字节及缺口识别正确”，不意味着法律审查通过：`legal_clearance=false`、`release_eligible=false`。正式审阅还需取得并核对原始包/源码许可正文、各原生组件的归属与传递依赖、必要的源码提供方式及最终产品级 LICENSE/NOTICE。按 [DEC-20261001-575](../decisions/decision-log.md) 保留固定候选不变，下一独立项先定位矩阵中 61 条许可原始字节并核对来源，为新非发行侧载候选做准备；不在本项直接升格发行。兼容性：无运行变更；升级：无迁移；回滚：弃用审计工具/清单，历史候选仍在。
