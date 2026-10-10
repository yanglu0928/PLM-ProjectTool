# SOL-01-A04-P07-P04：Windows 11 Reference 真实浏览器/PG 组合

日期：2026-10-09；结果：`REFERENCE_BROWSER_PG_PASS`，限定 Windows 11、本机真实 Edge、一次性隔离 PostgreSQL 18.6、合成 License/Session/私有文件；不是正式生产发行验收。

编码前检查：Phase 2 Platform Core；输入冻结 API-04、CR-SOL-008、P07-P01～P03；前置后端 Owner/HTTP/PG 与前端类型/构建均通过。涉及只读浏览器验证夹具，不新增实体、Schema、生产 API 或权限。验收为真实 Edge 与真实 API/PG 同源组合，候选→详情→固定 DocumentVersion 独立鉴权→Evidence Viewer 定位，撤销 Session 后重读 401 且隐藏原文链接。风险为仅合成账户/License、无真实人工确认和正式目标账户材料。

复用既有 PROJECT Reference 创建夹具，在私有测试目录生成真实 DocumentVersion、Evidence、Reference 和成员 Session；临时 FastAPI/前端构建同源服务只挂载本次所需只读路由，Node 驱动一次性 Edge profile。浏览器先恢复只读身份，依次访问候选、详情、固定文档版本和 Evidence Viewer；核对相关 API `200` 与固定版本链接。删除测试 Cookie 后刷新详情，实际 Reference GET 返回 `401` 且来源链接消失。退出时停止服务、Edge 和本轮隔离 PG，清理一次性目录。

首轮夹具把 Evidence 内容链接误假定为 Evidence 专属路径，实际服务端返回的是已固定 DocumentVersion 内容端点；修正测试断言后两轮复验通过。此为验收脚本假设偏差，不是生产路由变更。最终脚本 exit 0：`REFERENCE_EDGE_PASS`、`SOL_01_A04_P07_P04_REFERENCE_BROWSER_PG_PASS`，前序真实来源/创建 PG 回归同时通过。前端 P07-P03 全量 `103 files / 1614 tests`、typecheck/build 已通过，本轮位置文案补测 2/typecheck/build 通过。

兼容性/升级：仅新增隔离验证脚本和记录，无生产代码/Schema/依赖变化，无升级动作。正式 License/服务账户、客户人工确认、Windows Server 2025、20 并发与性能、Gate 3、可用程序包仍待。Debian 13 按用户指令跳过；不能据本轮 Edge/PG PASS 推断三平台发行或 UAT 通过。

TraceLink：API-04 → CR-SOL-008 → P07-P01～P03 → P07-P04 Edge/PG/撤权 → 后续 GLOBAL 人工确认入口与发行验收。
