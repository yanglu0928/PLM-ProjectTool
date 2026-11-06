# OUT-01-A01-P40 编码前检查：真实 FastAPI/PG18 到 Edge 下载保存单进程闭环

- 日期：2026-11-06
- 状态：PASS_WITH_LIMITATION，可进入验证器实现
- Change Request：CR-OUT-035
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P40

## 目标与路线核对

P38 已用 Hosted PostgreSQL 18、真实 FastAPI Artifact 引用与 Document 下载路由、SQLAlchemy Repository、Storage 和合成文件验证了HTTP响应字节/hash/大小/MIME与失败关闭；P39 已用真实Edge、同run生产前端和合成同源HTTP夹具验证按钮、下载落盘及文件hash。二者仍是分层证据，没有从浏览器经过同一实时后端服务连接到同一PG/文件实例。P25 已在 GitHub Hosted D盘完成真实 Edge→loopback→Output Create API 的失败关闭路径。最新全链 run [42224244339](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42224244339) 为 success，包含P25/P39及构建验收。

按 CR-EXEC-002 的最短纵向链优先规则，继续验证输出历史下载链的实时网络组合，不等待正式Publisher trust；正式信任缺失仍禁止真实生成/插件执行/生产装配。

## 编码前检查

- 冻结基线：API Contract V1 的 OutputArtifact 固定引用、Document受保护下载合同；P38/CR-OUT-033；P39/CR-OUT-034；P25/CR-OUT-021。
- 当前实现：Windows显式平台组合有opt-in的Output读、Artifact引用与Document下载路由；P38已有真实PG18/Storage route verifier；P39有Edge真实下载Harness；P25有Hosted loopback HTTP bridge、PG18与Edge runner边界检查。
- 本WBS只新增P40 Hosted验收器及workflow追踪。Harness启动真实FastAPI ASGI服务并监听仅loopback随机端口，连接本轮隔离PG18和D盘合成Storage；Edge加载同run production frontend，通过真实Artifact引用/Document内容GET下载合成文件。合成Session/License仅为测试夹具，不接正式默认组合。
- 不改产品路由、API/Schema/Migration、权限/License/Publisher信任；不创建真实生成任务、不运行插件、不访问客户正文或外部AI。
- 专项用例必须覆盖：授权Artifact→内容流→Edge落盘字节/hash/长度/MIME一致；非成员/跨项目/未知Artifact不返回正文且不触发内容下载；损坏Storage内容失败关闭且不泄露locator；确保Host、路径、临时文件及PG数据均限定于runner D盘/loopback，finally清理可判定。
- 全量Hosted回归要求：前后端测试/typecheck/build、wheel、父包PG18/pgvector、A17/A34/A35/P24/P39/A50及Secret检查。不能因独立失败job虚报整体全绿。
- 风险：Windows Server 2025 Hosted网络/Edge不是Windows 11设备证明；合成身份不是生产trust；此项不证明真实生成、正式Pilot、Gate或Release。若同一实时服务组合前置缺失，先记录具体限制并只实现不越权的最小测试接线。
- 回滚：移除P40验证器及专属workflow接线；不删除产品数据或修改产品API/Schema/信任边界。

## 实施决定

按用户持续授权，先记录CR-OUT-035与本检查，再实现并仅在GitHub Hosted Windows Server 2025 D盘/云端执行验证。本项目标是补足同一实时服务组合证据；不是宣布Pilot可用或正式发行。
