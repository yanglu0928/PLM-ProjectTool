# P07-A24 UserRead逐边证据

2026-09-27 Windows11/Python3.13.15/coverage7.13.5，exit0。三个现有参数化方法分别coverage与独立trace两轮3/3通过，额外noCommit与UOW退出断言通过。只收行号/异常事件类型，不收locals/私有消息。

|Guard/raise|异常事件数|实际coverage跳转|仍缺统计坐标|
|---|---|---|---|
|62|4|62→60、62→63|62→72|
|64|3|64→60、64→65|64→72|
|66|1|66→60、66→67|66→72|
|67|1|67→60、67→68|67→72|
|69|1|69→60|69→72|

证明这五个拒绝已执行，不表示全Auth其他缺口都是测量问题；不降低90%或排除文件。原A21 raw保持，完整Auth最近86.235%仍未通过。仅Port合同，不冒充SQL或生产信任源。完整unit/15链coverage、性能、wheel未重跑，无生产/Migration/API/依赖变化，无升级。追溯DEC-20260927-372及同名progress/validation，下一五guard AST等价分行及真实详情链。

新独立raw SHA256：`7ba3da10c2e283f9f620b38c8fcf2470ed6ccb4adbe928b10f2060fb7f699a1b`；旧A21重验`18ef6f24069eeb56bd306a50b0fc76ba4900f17f2c8e0b44965c144f138c3b22`未变。原始报告与诊断仅本地保留，不上传运行产物。
