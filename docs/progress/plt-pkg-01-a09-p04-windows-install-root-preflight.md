# PLT-PKG-01-A09-P04：Windows候选安装根路径前置拒绝

日期：2026-10-01；状态：`RULE_INTERNAL_PASS / INSTALLER_INTEGRATION_OPEN`。

编码前检查：Phase 2 / 本 WBS；输入为 [A09-P03 路径实测](plt-pkg-01-a09-p03-unified-windows-ocr-smoke.md)与发行建议路径`C:\PLMTool`。仅新增可复用的安装根路径校验，不改服务、Parser、实体、API、权限、ORM/Migration、正式安装/升级工具。验收：建议路径通过，非ASCII/UNC/相对路径/盘符根/路径穿越/Windows保留名称和非法组件在任何复制前拒绝；退出码0/2清晰。风险：这只是后续安装器应调用的规则，尚未与不存在的正式安装/升级入口接线；弃用此工具即可回滚，历史包不变。

`tools/windows_install_root_preflight.py` 对当前候选强制绝对ASCII盘符路径，拒绝中文仓库路径及不安全Windows组件，成功仍声明`release_eligible=false`。定向单测2/2通过；CLI `C:\PLMTool`返回`WINDOWS_INSTALL_ROOT_PREFLIGHT_PASS`，`D:\AI工具\PLMTool`返回`REJECTED`/退出2。没有执行任何安装、复制、升级或生产数据变更。

下一项应把该规则作为正式安装与升级入口的前置调用，并在Windows11/Server2025实际目标账户复验；若未来更换支持Unicode的新Tesseract，应建立来源/许可/质量证据后才能放宽，不能仅删除规则。完整离线安装、NOTICE/对应源码、签名/License、真实质量、Server2025/Debian13和Gate仍待；`release_eligible=false`。
