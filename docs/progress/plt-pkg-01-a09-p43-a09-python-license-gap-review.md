# PLT-PKG-01-A09-P43-A09：Python 许可表达式空项的材料映射

日期：2026-10-01；状态：`PYTHON_LICENSE_EXPRESSION_GAPS_MAPPED_REVIEW_REQUIRED`。固定输入为 P43 Ghostscript 源码非发行候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、P33/P22 祖先候选及原生 PE 证据矩阵。候选谱系和输入矩阵先经现有 P43-A07 审计，再执行[只读映射工具](../../tools/audit_python_license_expression_gaps.py)。

编码前检查：Phase 2，Gate 3 未关闭；前置 P43-A07/A08 的材料核验已完成。本项不改候选、业务实体、API、权限、Schema、Migration、SCM 或生产文件，只从精确包内 `METADATA`、第三方库存、嵌入通知与独立侧载生成[60 行逐组件审阅清单](plt-pkg-01-a09-p43-a09-python-license-gap-review.csv)。验收为每行名称/版本与唯一 `METADATA` 匹配、库存声明文件真实存在、无静默提升法律状态；风险是将字段空值误判为无许可，或将文件存在误判为义务已满足。

真实固定包审计退出 0，定向单元 5/5 通过。60 项 `license_expression` 空值逐项映射：57 项有包内嵌入通知文件，2 项仅有独立侧载（`et_xmlfile`、`openpyxl`），1 项无专属通知材料（`bce-python-sdk`；其通用 Apache 正文复用候选另见[P43-A08](plt-pkg-01-a09-p43-a08-bce-license-text-reuse.md)）。其中 53 项有旧式 `License` 元数据字段、40 项有许可证分类器；两种元数据可能重叠，不能相加为已确认许可总数。全部 60 项的 `review_status` 仍为 `REVIEW_REQUIRED`。清单记录精确路径，不复制客户数据或秘密，也不推断各组件最终许可证或版权归属。

选择将嵌入文本、独立侧载和无专属文本分开映射；即使存在多个材料，也不将其自动合并为“已审结”。这属于 [DEC-20261001-572](../decisions/decision-log.md) 的只读审计决策。兼容性：只增审计工具、测试与文档，不改运行或包字节。升级：无迁移。回滚：撤新工具/清单，本次固定候选历史保持不变。产品级 LICENSE/NOTICE、合格法律复核、正式信任源、目标平台和 Gate/UAT 仍开放，`release_eligible=false`。下一项核对其余有 `license_expression` 的 Python 第三方包材料，完成 105 项全量审阅输入，而非仅凭本 60 项宣布放行。
