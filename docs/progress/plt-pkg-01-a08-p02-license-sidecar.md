# PLT-PKG-01-A08-P02：原 wheel 许可文件补充归档

## 编码前检查

- 当前 Phase：Phase 2 Platform Core；非发行准备。
- 当前 WBS：PLT-PKG-01-A08-P02。
- 输入基线：A01 原 wheel 固定 Hash、A07 非发行 ZIP、A08-P01 精确对账结果。
- 前置任务：A08-P01 93/93 身份/Hash 核对通过；许可审查与 Release Gate 未通过。
- 涉及模块：独立本地补充归档工具；无实体、API、权限、Schema、Migration 或生产安装修改。
- 验收标准：原 wheel 每份许可/通知材料按原始字节保存，写入来源 wheel Hash 与文件 Hash，回读逐件一致；错误 Hash、伪发行状态和覆盖已有输出失败关闭。
- 风险：补充归档不等于 A07 ZIP 已含这些文件，更不构成法律合规或最终安装包；旧候选不覆盖。撤独立工具和经路径核对的本地 Git 忽略新归档即可回滚。

## 结果

- `py -3.13 -m unittest tools.tests.test_build_windows_license_sidecar tools.tests.test_audit_windows_candidate_licenses`：7/7 PASS。
- 从 A01 93 个原 wheel（Hash 重新复核）抽取 152 份许可/通知文件，逐文件 SHA-256 及来源 wheel SHA-256 写入 manifest；ZIP 回读 152/152 一致。补充归档 `artifacts/package-prep/windows11/embedded-candidate-c81aa7bff37a/NOT-FOR-RELEASE-wheel-license-sidecar.zip`，SHA-256 `550be0a3411286b216fc031255f03a3cb70875eb0fe7e79bfaba4480b1c8fdd2`，仅本机 Git 忽略目录，不推送二进制。
- A07 旁装遗漏的 `et_xmlfile` 两份、`openpyxl` 一份已包含在补充归档；A07 原 ZIP 保持原样，所以尚须后续组装进新的候选并验证安装路径。
- `bce-python-sdk 0.9.79` 原 wheel 与自有产品 wheel 仍无许可文件；前者仅有旧式 Apache 2.0 元数据与未绑定精确版本的上游主分支许可参考，后者的产品开源许可尚未选择。两项不被本归档伪补齐，`REVIEW_REQUIRED` 保持。

## 结论和后续

`WHEEL_NOTICE_SIDECAR_INTEGRITY_PASS / RELEASE_BLOCKED`。这是原始材料的可复核保存，不是完整 SBOM 或合规批准。下一项 `PLT-PKG-01-A08-P03` 应将补充材料纳入新候选、验证 152/152 存在及文件 Hash，同时继续核查前端、系统/原生组件、模型与正式产品许可；A07 旧 ZIP 不修改。
