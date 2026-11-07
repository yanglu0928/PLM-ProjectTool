# OUT-01-A01-P39 Hosted Edge 下载保存验收结果

- 日期：2026-11-06
- 结论：PASS_SCOPE_LIMITED
- Workflow run：[42156574221](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42156574221)
- 源码提交：`5cb5c8114c314895212462dec4c045c65141a720`

## 验收结果

- Hosted Windows Server 2025 Edge 加载本run production frontend dist，通过合成登录和输出历史页面。
- 仅 `SUCCEEDED` 合成输出显示“下载文件”入口；点击后真实执行固定Artifact引用GET，再按Document attachment响应下载。
- Edge实际保存文件为50字节，与合成负载逐字节一致；SHA-256为 `90130db205e86ba6bec3b8a2d90161db16b34f27226ceca67e206aa8eb923437`。
- `FAILED` 输出无下载入口。跨项目引用在Document内容GET之前失败关闭，未保存文件。
- P39产品fetch receiver调用修复在上述原始点击路径被实际验证；仅Harness阶段/异常类别诊断，不记录凭证/正文。

## 独立复核与范围限制

本结论是Hosted Edge对同源合成HTTP fixture、真实浏览器下载与安全拒绝边界的验收。它不是P38真实FastAPI/PG18路由与Edge处于同一实时产品进程的端到端验证；不证明正式Publisher/License trust、Windows 11实机、生产后端启动、Pilot、Gate或正式Release。

同一workflow其余主要构建、测试、PG18 sidecar/父包烟测及P24/A17/A34/A35/A50成功。独立P25仍因initdb.exe以 `3221225781 / 0xC0000135`退出而失败，真实HTTP/Edge没有执行；因此整个workflow为failure，P25为BLOCKED_DIAGNOSTIC。

## 后续

按CR-OUT-021/本次P25编码前检查，下一项仅在P25相同Hosted Windows job、同run父包ZIP和D盘Runner Temp中，运行既有父包PG smoke helper作差分。该诊断不会重试旧flags/PATH猜测；Pilot/Gate/Release状态维持原样。
