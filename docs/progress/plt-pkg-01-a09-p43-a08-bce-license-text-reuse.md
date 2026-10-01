# PLT-PKG-01-A09-P43-A08：bce-python-sdk 精确许可文本复用核对

日期：2026-10-01。范围：Windows 11 固定非发行候选、原始 `bce-python-sdk 0.9.79` wheel/sdist，以及 Apache 官方 2.0 许可证正文。结论仅为技术材料审阅候选，不是法律意见或发行批准。

## 固定输入与验证

|输入|SHA-256|
|---|---|
|P43 非发行候选 ZIP|`764d2f84c8da9fa8a58a521026502f397dcb0602a3e48e9ac702c8e95a9cb7a5`|
|`bce_python_sdk-0.9.79-py3-none-any.whl`|`71799ac8740505e0759d30873f6f1a478fa8f83aedf425d511f1419a5f30082e`|
|`bce_python_sdk-0.9.79.tar.gz`|`cd77476b43347ed28d0211d5ad557e524e1ec648bd093d57c6a6d3de075a7508`|
|[Apache 官方 2.0 正文](https://www.apache.org/licenses/LICENSE-2.0.txt)|`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`|

只读工具 [`audit_bce_license_text_reuse.py`](../../tools/audit_bce_license_text_reuse.py)先验证 P43/P33/P22 候选谱系，再核验上述原件、包内元数据和现有侧载。原 wheel/sdist 均无独立 `LICENSE`/`NOTICE`；固定候选元数据为 `Name: bce-python-sdk`、`Version: 0.9.79`、`License: Apache License 2.0`，无 `License-Expression`/`License-File`。候选中的 `payload/third-party-licenses/caddy/LICENSE` 与官方 Apache 2.0 正文逐字节一致。原源码头部等更完整的出处核查见[前序记录](plt-pkg-01-a08-p04-bce-exact-source.md)。

真实固定候选审计退出 0，定向单元测试 3/3 通过，输出状态为 `BCE_DECLARED_APACHE_TEXT_REUSE_REVIEW_CANDIDATE`。这只说明无需为“通用 Apache 正文”再复制相同字节；现有路径仍标为 Caddy，**没有 bce 专属归属/通知映射**，也没有最终法律审查与签核。因此 `legal_clearance=false`、`formal_notice_approved=false`、`release_eligible=false`。

## 差异、风险与下一步

本项无架构、数据模型、Schema、API、权限、依赖或安装载荷变化，无迁移。按 [DEC-20261001-571](../decisions/decision-log.md)，只把正文复用列为审阅候选，保留固定 ZIP 不变；回滚可弃用工具与本记录。正式 NOTICE 必须逐组件明确名称、版本、归属、许可证文本及适用分发义务，并与最终发行包绑定，经过合格复核；不得因元数据声明或共用正文而标为 PASS。下一独立项逐一核对其他 Python 包的许可表达式空项与既有材料，正式信任源、目标平台、Gate/UAT 仍分别开放。
