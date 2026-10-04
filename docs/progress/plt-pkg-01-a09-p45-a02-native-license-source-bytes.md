# 原生 OCR 许可文本的原始来源字节核验

日期：2026-10-01；任务：PLT-PKG-01-A09-P45-A02。本文为后续非发行侧载候选准备可复核的原始字节输入，不是对各 DLL 适用许可证、对应源码义务或整包法律合规的判断。

以 P43 候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P33/P22 谱系及[34 项原生 PE 矩阵](plt-pkg-01-a08-p09-p05-p03-a07-p03-no-jbig-license-evidence.csv) SHA-256 `a16312f5a322e21ad1f818fa7848a6f2b8f9f000add3b893f2b3a1e02fed15bc` 为固定输入。编码前检查：Phase 2/Gate 3 未关闭；只从本地 Git 忽略区的 MSYS2 精确二进制包与上游源码归档读取，未改候选、业务实体、API、权限、Schema、Migration 或正式安装。风险是历史已解包目录可能偏离原始压缩包，因此[只读工具](../../tools/audit_native_license_source_bytes.py)重核归档 SHA，并从归档成员直接取字节比对；包成员另与已解包副本逐字节核对。

实际核验 61 条矩阵文本记录均匹配：53 条来自固定 MSYS2 `.pkg.tar.zst` 成员，7 条来自三份历史回退的上游源码归档，1 条来自固定 libtiff 4.7.2 上游 tar。共涉及 42 个不同正文 SHA-256 与 34 个固定归档。每条的对应二进制、归档路径/哈希、成员路径与正文哈希见[逐条来源清单](plt-pkg-01-a09-p45-a02-native-license-source-bytes.csv)。固定候选与矩阵先验、实际源包读取退出 0，定向单元 4/4。

42 个不同哈希不等于 42 项独立许可证：相同正文可被多个二进制共享，部分源材料包含 `README` 或多种许可文本，适用范围仍待合格复核。原 P43 候选未追加这些原生组件的专属侧载，34 项 `release_obligations_reviewed` 仍为 `NO`，`legal_clearance=false`、`release_eligible=false`。按 [DEC-20261001-576](../decisions/decision-log.md)，下一项在新非发行候选中按组件/来源建立独立侧载与清单，同时保留旧候选和全部未审结标记。兼容性：无运行变化；升级：无迁移；回滚：弃用本次只读审计资料，原始归档与历史矩阵不变。
