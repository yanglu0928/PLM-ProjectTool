# 原生 OCR 通知候选随包登录链隔离验证

日期：2026-10-01；WBS：`PLT-PKG-01-A09-P45-A07`；结果：`SYNTHETIC_NATIVE_OCR_NOTICE_PACKAGED_PLATFORM_WRITE_HTTPS_PASS`。

本项检验固定新候选在 Windows 11 隔离环境中能否启动随包 Python、Caddy 与临时 PostgreSQL，并经合成 HTTPS 完成登录、Session 和许可拒绝。输入为 P45-A04 清洁暂存、P45-A05 原始隔离布局、固定新候选 SHA-256 `30c9d59852af7e7a9360c4e6f36eff815eb134c481b5908786898b315426bf98` 及 P43/P33/P22 谱系。12 个固定 SecretKey Vault 目标和数据库凭据目标先检查为空；新布局在全新 Temp 目标中重建并再次核对 21,161 件全量映射/哈希，然后才注入一次性合成公钥。候选 ZIP 本身不改，合成私钥不入包。

随包 Python 以显式 `--platform-write` 启动，包内 Caddy 使用临时证书，临时 PostgreSQL 18 完成初始化和 Migration。真实 HTTPS 登录返回 200，Session 返回 200，无有效 License 的 Project 读取返回 403；错误 Host 和 Origin 也被既有测试断言拒绝。运行结果报告 42 份许可正文、61 条映射、`fixed_candidate_unmodified=true`、`formal_trust_provisioned=false`，真实退出 0。定向新旧单元 4/4。脚本断言临时进程停止、临时文件删除、合成 Vault 目标不残留；独立读回确认新测试目标和正式 `C:\PLMTool` 均不存在。

为复用 P42 的严格临时数据库/Vault/清理边界，只新增可选布局验证与重建函数参数；原 P42 默认回调不变。此项不代表正式公钥、License、证书、目标服务账户、SCM、Server 2025 或 UAT 已验收。无业务 API、Schema、Migration 或生产数据变更；失败时仅清理本次临时资源，历史候选不变。`release_eligible=false`、`legal_clearance=false`。下一项优先汇总发行阻断证据与责任边界，避免将技术候选误当成可发行产品。
