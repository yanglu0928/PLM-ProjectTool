# OUT-01-A01-P37：输出历史受控下载入口结果

- 日期：2026-11-06
- 结果：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-032
- Hosted run：[42126880417](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42126880417)
- 分支：feature/p51-a33-launcher-checksum-recovery

## 交付

输出历史仅在 SUCCEEDED 请求上显示“下载文件”。前端通过 P36 的项目范围 Artifact 引用读取 Client 重新取得授权固定引用，精确验证请求、项目、文档版本、Artifact/MIME、Hash/大小和同源内容路径后才导航至现有 Document 内容流路由。读取失败或页面权限变化时不导航，不自动重试。无后端/API/Schema/Migration变更。

## Hosted 验收

- 前端：205 test suites / 2,098 tests；typecheck和生产build通过。
- 后端：4,087 tests及wheel通过。
- PostgreSQL 18.6 / pgvector 0.8.6父包 smoke：P36固定绑定 available_binding=PASS，跨项目和未知请求均隐藏；无数据库变更。
- 父包组装、临时PG生命周期、A17、A34、A35、P24、A50成功。
- 整体15个jobs中14个成功；独立P25 HTTP/Edge失败于initdb.exe，exit 0xC0000135，没有启动真实HTTP/Edge。因此workflow非全绿。

## 限制

前端测试以合成Client/导航验证，不证明浏览器实际取得并保存文件字节。正式Publisher/License trust仍未具备，opt-in路由未默认挂载；没有Windows 11实机、Pilot、Gate 3、UAT或正式发行证据。P38将以合成PostgreSQL 18和受保护HTTP组合补实际Document内容流集成验证。仅GitHub Hosted D盘运行；用户本机/C盘未运行项目代码。
