# SOL-05-A03-P03：SectionVersion 历史公开读取合同

日期：2026-10-12。结果：`SECTION_VERSION_READ_HTTP_CONTRACT_PASS`；仅可选 HTTP Router，Windows 运行组合及真实网络/数据库验收留下一 WBS。

## 编码前检查与范围

Phase 2；输入 Gate2 冻结 API-04、CR-SOL-003、A03-P01 项目成员授权及 A03-P02 内部历史读取 Owner，前置满足。单一问题是将两个已冻结 GET/LIST 路径接入安全、可分页的 HTTP 投影。不变更 Schema/Migration、角色、CREATE、冻结路径、依赖或历史数据。风险是游标跨 Session/资源复用、列表泄露声明正文、独立只读 Router 遮蔽 CREATE，以及把历史来源误说成现时资格；实施前登记 DEC-1183。

## 实施与验证

新增独立 32 字节 HMAC-SHA256 SectionVersion 游标，绑定资源族、Session、Project、Section、页大小及下页版本号；畸形、篡改、跨域游标失败关闭。可选 Router 保持默认 404，现时 Host/Session 检查后由内部 Owner 每次验证 License 与 Project 成员；LIST 仅返回元数据和计数，GET 返回固定正文引用、Requirement/Evidence 引用与声明，不返回文件路径、来源正文或现时资格结论；均 `no-store`。独立只读装配的 POST 显式 404，既有 CREATE 先装配，联合装配时原 POST 保持可达。

定向 SectionVersion 读/写 API 合同 7 项、32 子测试通过；默认关闭、页/详情投影、错误映射、篡改/跨 Session/跨 Project/Section/页大小、Host/匿名、CREATE 共存均覆盖。后端全量回归 3543 通过、3 跳过、5573 子测试通过（95.41 秒）。无真实 PG/Windows/Edge 验证，本项不能据此宣称 Pilot 可用或 Gate3 通过。

兼容/回滚：无迁移及旧数据变化；撤除可选 Router 注入可关闭 GET/LIST，独立密钥供给尚未装配，历史保留。下一项 `SOL-05-A03-P04` 验证真实 ASGI/PG 读链和 Windows 可选装配前置。正式 HTTPS/目标账户/公钥、Server2025、性能、Gate3/Pilot/Release 仍未验；Debian13 实机依用户指令跳过。TraceLink：Gate2 API-04 → CR-SOL-003 → A03-P02 → DEC-1183 → 本 P03 → P04 → Gate3/Pilot。
