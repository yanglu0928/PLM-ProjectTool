# Python 第三方包完整许可材料审阅输入

日期：2026-10-01；任务：PLT-PKG-01-A09-P43-A10。本文供发行负责人及合格法律审阅人员使用，汇总固定 Windows 11 非发行候选中 105 个 Python 第三方分发包的精确元数据与通知材料位置。它是审阅输入，不是完成的法律审查、最终 NOTICE 或发行批准。

## 输入与核对结果

输入为 P43 候选 SHA-256 `764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`、其 P33/P22 祖先候选及原生 PE 证据矩阵。只读[核对工具](../../tools/audit_python_declared_license_materials.py)先重验候选谱系，再读取 106 个 Python 分发包的库存；剔除 1 个自有后端后，对 105 个第三方包逐一匹配唯一的名称、版本与包内 `METADATA`。

此前 60 项无 `license_expression` 的核对结果与新增 45 项有声明的核对结果合并为[105 行完整清单](plt-pkg-01-a09-p43-a10-python-105-review-inputs.csv)，无重复或遗漏。新增 45 项的库存声明均与对应 `License-Expression` 头完全一致；全部 `License-File` 头指向库存已列明且候选内真实存在的嵌入文件。45 项涵盖 14 种原样声明表达式，包括 `AND`/`OR` 组合；工具没有把这些表达式自动归并为单一许可证结论。

105 项按材料位置分为：102 项有嵌入通知文件，2 项仅有独立侧载，1 项无该分发包专属通知材料。缺项是 `bce-python-sdk`；其通用 Apache 正文复用候选另见[P43-A08](plt-pkg-01-a09-p43-a08-bce-license-text-reuse.md)，仍待专属归属映射与法律复核。所有 105 项保持 `REVIEW_REQUIRED`，`legal_clearance=false`、`release_eligible=false`。固定候选审计退出 0；本项定向单元 4/4，上一项映射回归 5/5。

## 限制与交付影响

清单的路径和头部一致性只证明“这些精确字节及声明存在”，不证明文字覆盖所有传递依赖、原生扩展、版权归属、源码提供或发行场景义务。产品级 `LICENSE` 与最终 `NOTICE`、合格复核人和签核记录仍缺；即使 Python 105 项审阅输入齐全，也不能因此放行整包。另有 Ghostscript、Caddy/Go、PostgreSQL/pgvector、前端、原生 OCR 和模型的独立法律审阅队列。

本项按 [DEC-20261001-573](../decisions/decision-log.md) 只增加审计工具、测试和审阅清单，不改业务程序、固定发行候选、API、Schema、权限、SCM 或安装根。无 Migration；回滚可弃用新审计材料，既有候选与历史版本不变。下一独立任务转向 Windows Server 2025 虚拟机的只读连通与安装前置核查，不能用 Windows 11 结果默认替代 Server 2025 验收。
