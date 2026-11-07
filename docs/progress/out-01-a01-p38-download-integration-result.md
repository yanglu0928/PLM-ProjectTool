# OUT-01-A01-P38：OutputArtifact至Document内容流受保护HTTP纵向验收

- 日期：2026-11-06
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-033
- Hosted run：[42139905574](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42139905574)
- 分支：feature/p51-a33-launcher-checksum-recovery
- 代码提交：c80e504e6635c8d3141323db67b60d415c8a8b6f

## 验收范围

在GitHub Hosted Windows Server 2025 D盘临时环境和clean PostgreSQL 18父包smoke中，运行实际Artifact引用HTTP与Document内容下载HTTP路由、SQLAlchemy Repository、Document读服务、PrepareDownloadService及LocalFileStorage。Session、Project授权摘要和License guard为合成夹具；数据库和文件均为Runner临时数据。

## 结果

父包PG18的 output_artifact_document_download_http_validation 摘要全部通过：

- 授权Artifact固定引用HTTP响应符合标准 {data, trace_id} 封套，且匹配请求、项目、Document/Version、Hash、长度和固定同源内容URL。
- 真实受保护Document路由流出的字节与磁盘合成文件完全一致，Hash、长度和MIME一致。
- 未知/跨项目Artifact与跨项目Document内容均隐藏；篡改存储文件后正文不流出。
- Storage locator不披露；客户数据为false、外部调用为0、正式信任未使用、数据仅位于Runner临时目录。

## Hosted全链

- 15 jobs中14个成功：Backend 4,087 tests/wheel；Frontend 205 suites/2,098 tests、typecheck和build；clean parent PostgreSQL 18/pgvector smoke、父包组装、A17/A34/A35/P24/A50成功。
- 独立P25 job在 initdb.exe 数据库初始化前以 0xC0000135 退出，stdout/stderr为空，data目录未创建；真实HTTP/Edge步骤未运行。整体workflow因此非全绿，P25继续BLOCKED_DIAGNOSTIC。

## 限制与下一步

该验证通过ASGI原生scope执行真实HTTP路由及StreamingResponse，未打开loopback TCP连接；Session/License不是生产信任，未在浏览器保存文件。没有Windows 11设备、正式Platform trust、Pilot、Gate 3、UAT或Release证据。P39将单独验证Hosted Edge经输出历史入口实际保存附件及字节/Hash契约；P25真实产品HTTP/Edge仍独立阻塞。未在用户本机或C盘运行代码。

## 变更清单

- Changed：父包PG18验证器接入真实Artifact→Document HTTP/存储链；仅测试辅助与追踪文档变更。
- Files：validation/out_01_a01_p38_download_http/verify.py、P33 smoke接线，以及CR、STATUS、结果文档。
- Migration/API：无Migration，无API合同或生产接口变更。
- Tests：P38父包PG18专项PASS；整条Workflow 14/15 jobs通过但因P25失败为非全绿。
- Known issues：P25 Windows initdb 0xC0000135；loopback TCP/Edge/Win11/正式trust未验。
- Next：OUT-01-A01-P39 Hosted Edge实际保存验收。
