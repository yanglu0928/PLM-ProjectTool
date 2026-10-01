# EVD-01-A04-P03-A09：资格 UI 真实浏览器验收前置核查

日期：2026-10-01；Phase 2 Platform Core；结论：`BROWSER_PRECONDITION_BLOCKED`，不是资格 UI/UAT PASS。

当前目标是通过真实浏览器，在 Windows 显式平台写组合中操作固定原文定位、人工资格提交、未知回执恢复，并回查 PostgreSQL 的资格状态、幂等收据和 Audit。输入为 A05～A08-P02 的合成 PostgreSQL、HTTP、前端合同证据；不改变冻结 API、Schema、权限或业务事实。

本轮按 computer-use Skill 初始化 `@oai/sky`，运行时在执行任何浏览器动作之前返回 `failed to write kernel assets: 系统找不到指定的路径。 (os error 3)`。此前 PDF 页级浏览器验证遇到相同错误。本轮未启动浏览器、未上传文件、未提交人工资格、未读取真实 Audit；因此不能用前端测试或合成 ASGI/数据库验证代替 A09 的浏览器结论。

风险与后续：运行时恢复后，只用合成 Evidence/Document 和隔离 PostgreSQL 执行浏览器矩阵，核对同源内容/固定版本、PM/CustomerManager 可见性、普通成员与撤权拒绝、首次提交与刷新、同 Key 回查、未知回执不重复提交和单份 Audit。正式目标账户材料、HTTPS、Server 2025、Debian 13 与客户 UAT 仍分别验收；任何真实客户正文/密钥不因本项发送到外部。当前转向其他独立 Phase 2 工作，不关闭 Gate 3。
