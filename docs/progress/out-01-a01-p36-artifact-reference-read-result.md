# OUT-01-A01-P36：OutputArtifact固定引用读取接口验收结果

- 日期：2026-11-06
- 结论：PASS_SCOPE_LIMITED
- 代码提交：c769862df797ab421ed2f03ee3633382f9a8d428
- GitHub hosted run：[42121003242](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42121003242)，Windows Server 2025 hosted runner，D:临时空间。
- 变更追踪：CR-OUT-032

## Changed / Files

新增OutputArtifact授权读取Application Service、PostgreSQL Repository、opt-in HTTP GET和Windows Output read composition。新增Application/SQL projection/HTTP/Windows组合单测，并在P33 PG18 smoke成功后调用新Repository的P36 verifier。
关键文件：output/application/read_artifact.py、output/infrastructure/read_artifact_repository.py、output/api/read_artifact.py、entrypoints/windows_output_read.py、validation/out_01_a01_p36_artifact_read/verify.py。
Migration：无。既有OUTPUT_REQUEST_GET/LIST响应不变；新GET为 /api/v1/projects/{project_id}/output-requests/{output_request_id}/artifact。

## 验收证据

- Backend 4,087项全量测试与wheel通过；Frontend全量测试及production build通过。
- PostgreSQL 18.6/pgvector 0.8.6 clean parent smoke通过；真实Repository断言SUCCEEDED request、唯一AVAILABLE Artifact、Document/DocumentVersion/FileObject、Hash/大小绑定准确，跨Project和未知request均隐藏。
- Windows父包构建、A35、A17 packaged flow、A34离线替换/手动恢复、P24、A50、PG18 sidecar与embedded runtime检查通过。
- Workflow唯一失败为独立P25真实Output Create HTTP/Edge job；总体workflow非全绿，P25不属于P36前置，P25仍BLOCKED_DIAGNOSTIC。

## 限制与回滚

不暴露Storage locator/正文/Secret；文件字节继续由Document下载service授权并复核Hash/大小。Router仅opt-in并随受保护Platform组合装配；正式License trust仍阻塞平台完整装配。无Win11登录下载、用户验收或Pilot证据。P36不代表Gate 3/Release通过。
回滚为移除新read service/repository/router/composition和测试；不删除任何Artifact/Document版本，不更改Storage事实。

## 偏差记录

run 42118811778的两项测试fixture断言、run 42119917628 FastAPI延迟组合路径断言和helper模块路径偏差均先登记CR-OUT-032后修复。最终run 42121003242通过对应验收，没有放宽产品权限/数据边界。