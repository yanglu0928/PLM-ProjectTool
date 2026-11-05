# OUT-01-A01-P38 编码前检查：OutputArtifact至Document内容流的HTTP纵向验收

- 日期：2026-11-06
- 状态：PASS_WITH_LIMITATION（仅编码前检查）
- Change Request：CR-OUT-033
- 前置：P36与P37均 PASS_SCOPE_LIMITED；结果见 docs/progress/out-01-a01-p37-controlled-download-result.md。

## 已核实的实现事实

- create_windows_output_request_read_router 在同一受保护组合内挂载OutputRequest读取和P36 Artifact引用读取，两者复用Session、Project读取授权及License guard。
- production_login._create_production_app 仅在 include_secret_read 显式模式中构造Output read路由；同分支构造Document读取和 create_document_download_router，后者使用 PrepareDownloadService、Document读取授权、项目/License检查、有限并发、Hash/大小验证和流式响应。
- create_app 仅挂载非空router；Windows serve_windows --platform 显式选择受保护Platform app。login-only默认模式不会因本项增加下载路由。
- OutputRequestListView 默认使用严格 OutputArtifactReadClient 并导航到固定同源内容路由；P37 Hosted tests验证了UI/client行为，但使用模拟Client/导航，没有把真实HTTP Artifact引用和Document内容流字节贯穿到浏览器。
- 正式产品公钥/License trust仍是受保护Platform运行的前置条件。不能以合成信任替代正式信任，也不允许把该路径接入默认/login-only模式或据此宣称可用Pilot。

## 问题与决定

现有各层已存在且生产Platform只读模式会一起构造Artifact引用与Document下载服务；剩余证据缺口是：没有同一合成PostgreSQL 18环境中从授权Artifact引用HTTP响应到Document受保护内容流返回字节的纵向验收。P25真实Windows进程/Edge验收继续因独立 initdb.exe 0xC0000135 阻断；不修改或重启P25诊断路线。

决定：实施一项Hosted-only合成HTTP纵向verifier，使用既有Artifact/Document/下载路由工厂、临时PG18、合成Session/License和Runner临时data_root文件。验证授权成功、跨项目/非成员隐藏、未知/不可用Artifact失败关闭，以及内容Hash/大小/字节一致。尽可能通过现有生产composition adapter/route factory，不复制业务规则。没有客户文档、外部调用或本机代码运行。

## 边界、风险与回滚

- 不改冻结API合同、数据库Schema/Migration、default composition、生产trust或文件下载产品逻辑；新工件仅为验收脚本/测试和追踪文档，除非验收揭示生产接线缺陷。
- 合成License/Session只作为验证夹具，不视为生产信任来源。测试产物写入GitHub hosted Runner临时目录，完成后由runner清理。
- 若需要产品改动，必须先补充本CR：影响、兼容/迁移/回滚和定向测试计划后实施。
- 回滚仅删除P38 verifier/test/runner接线；不删除或修改产品生成文件、Artifact、Document历史或数据库事实。

## 验收计划

1. 独立验证器通过正式route factories和受保护HTTP契约运行在GitHub Windows Server 2025 hosted D盘/临时PG18；下载内容Hash/长度与固定DocumentVersion/FileObject一致，文件locator不进入HTTP响应。
2. 确认越权、跨项目、未知请求、非AVAILABLE Artifact和内容Hash不一致均不泄露正文或存储位置并失败关闭；query/range等不支持输入仍拒绝。
3. 全后端/wheel、前端全量/typecheck/build、父包PG18 smoke及A17/A34/A35/A50回归。P25独立失败不伪记P38通过，也不能阻止独立验收。
4. Secret扫描和GitHub同步后按证据更新STATUS/CHANGELOG/结果文档。未验收前不标PASS。
