# RAG-04-A06-P08：Windows 11 真实浏览器 Retrieval 闭环

日期：2026-10-04

状态：`PASS`

验证标记：`RAG_04_A06_P08_WINDOWS_BROWSER_PASS`、`RAG_04_A06_P08_WINDOWS_BROWSER_CLEANUP_PASS`

## Environment / Scope

- Windows 11 家庭版中文版 x86-64，build 26200；Microsoft Edge 154.0.4258.53；PostgreSQL 18.6/pgvector，端口 55434。
- 实际 Vite 生产构建经同源本地 Preview Proxy 访问生产 FastAPI `--platform-write` 组合；第四 `AI_PROVIDER_WORKER` 角色执行 Retrieval。
- 数据库、登录凭据、项目、文档、ACTIVE Index、query 和截图均为一次性合成验收对象；Retrieval 采用 `fts.project.v1 + none.v1`，零真实 Provider I/O、零客户数据外发。

## Result

真实 Edge 完成以下用户路径：登录 → 我的项目 → 项目详情 → 新建项目知识检索 → 提交首个 Run → 刷新并显示 Result/Context → 返回项目详情 → 创建第二个 Run → 提交取消 → 刷新显示 CANCELLED。

首个 Run 从页面创建为 RUNNING，随后由生产第四 Worker 单周期完成。页面只显示1条 `PROJECT_RECORD/FTS` 候选、整数最终分数、locator 和同源最小 Context；query 不在 URL、localStorage 或 sessionStorage，内部 bundle fingerprint 未进入前端 View。第二个 Run 使用当前 `v0` ETag 和单个幂等键直接取消，首次回执后再次读取当前状态为 CANCELLED。

浏览器观察到108个 API 响应事件，所需 Login、Project、Create、Get、Result、Context 和 Cancel 均为 2xx。三张最终全页截图完成视觉检查，未发现遮挡、截断、错误告警、query/密文/内部指纹或 Secret 泄露。

PostgreSQL 终检精确为：RetrievalRun `SUCCEEDED=1`、`CANCELLED=2`（其中1个是启动前经生产取消 API 关闭的旧合成夹具）；Candidate=1、ContextBundle=1、ContextItem=1、成功 Run 的加密 QueryContent=1。数据库、数据库连接、临时数据根、Windows 测试凭据和 Edge profile 全部清理；最终确认没有 `rag03a03p02_%` 临时数据库残留。

## Build / Evidence

- 前端构建沿用 P07 验收：69文件/1261项、TypeScript和Vite149模块 PASS。
- 构建 SHA-256：HTML `ae24ab097fcfe230b8d776efd3467eb27a7eae135f1e8692b026a2c2ed6d50e3`；JS `13e54218479ac1327036c48585f5c8c3f98b604d402cd9f1e416127d1258867f`；CSS `331b3c8b88e23b1273d38ea4a9c7056016aad60464072f32b00db25a297ef8af`。
- 最终截图 SHA-256：running `e2a27c3c72523960f0dfa07a16fcb7a467b81402ce1fc52d8b23fe5a55cbcb34`；result/context `27b53c4a4dfa10c6c1e2bfb577935a5a4f07928ef9276a9836e0851f3bf859be`；cancelled `e4f167d79fa42b32c875d528957373426991aac4aaf2a0e46351b8b6e5dc48d3`。
- 验收脚本 Python compile、两个 Node `--check` 及 `git diff --check` PASS。

## Deviations / Invalid Evidence

托管 Computer Use 浏览器内核两次因本机运行资产路径缺失失败；按既有可追溯替代方案改用本机 Edge DevTools Protocol 驱动同一实际构建页面。未改产品代码、未绕过认证，也未降低浏览器/API/数据库断言。

夹具与浏览器自动化在正式通过前出现五类无效证据：源正文不匹配既有 Embedding 指纹；生产凭据 URL 缺少密码被正确拒绝；整页导航使内存身份安全清空；同一响应式批次修改过滤与确认导致确认被正确复位；一次控制端等待耗尽40秒页面轮询窗口，但只读数据库证明 Run 已成功。分别改为精确合成正文、含随机非空密码的临时 Windows 凭据、应用内 RouterLink、分两步确认和120秒有界轮询。失败轮均未计验收证据并已清理，最终在全新库一次通过。

## Compatibility / Known Issues / Next

本项仅新增可复现验收脚本和证据记录，无产品 Schema、Migration、API、依赖或运行配置变化；可删除验证目录回滚，不影响业务历史。

`RAG-04` 首个 PROJECT/FTS-only 生产机制闭环完成，但不等于正式业务质量、性能、Windows Server 2025、Gate 3、UAT 或发行包通过。ACTIVE Index 列表 API、正式目标账户查询密钥和 Windows SCM 仍待；Debian 13 按用户指令跳过实机验证但仍为正式兼容目标。

下一项：`GATE-3-A01`，对 Phase 3 AI/RAG 的客观证据、历史质量失败、正式信任源/性能/平台缺口执行收口审计；不能满足的 Gate 条件保持 BLOCKED，并转入不依赖该 Gate 的后续计划任务。
