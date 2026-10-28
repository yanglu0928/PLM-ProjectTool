# PLT-PKG-01-A09-P51-A26：二次暂存验收失败记录

- 日期：2026-10-28
- 托管验证：GitHub Actions run 40628451209，PR #56，Windows Server 2025 hosted runner
- 组件结果：后端/前端、Python运行时、PG18/pgvector、embedded backend和父包组装均成功；D盘smoke失败，A26仍不得判PASS。
- 结果：标准certifi bundle及注释行正例已通过；新增恶意内容负例断言失败，stage_candidate报告“invalid public CA bundle content was accepted”。失败发生在候选暂存开始前的bundle内容验证，服务/数据库未启动。
- 当前证据不足以确认四个负例中的具体哪一项被接受；必须增加精确case索引诊断，仅暴露负例编号，不输出证书正文或Secret。猜测原因可能是检测实现/夹具格式不一致，不能用假设替代证据。
- 变更前修复计划：先从托管运行日志与源码复核原始负例字节，再为每个负例独立断言并返回固定编号；收紧PEM边界/证书解析，保证只接受ASCII空行、#注释和完整证书块，拒绝私钥标记、未知文本、非法Base64及截断块。不得放宽唯一文件路径或摘要检查。
- 运行计划：仅GitHub hosted Windows D:；修复前先推送本失败记录，再重跑云端完整后端/前端/组件/父包/暂存及旧回归。
- 偏差与状态：A26继续FAIL_LIMITED_REMEDIATION_RECORDED；无应用安装、生产API、业务库或真实License信任验证。Pilot/Release保持NOT_READY。

