# AUT-05-A12-P01 管理员User启停受控前端传输

2026-09-28 / 0.1.0.dev0 / PASS（前端传输合同）。

编码前检查：Phase2/Gate2已通过；输入冻结`AUTH_USER_ENABLE/DISABLE`、CR-AUT-006与既有Windows显式write后端，前置具备。DEC-419先登记；仅Auth前端SessionClient和单测，不修改实体/Schema/Migration/后端API/权限/依赖。验收固定路径、强If-Match、原Key、私有CSRF、无body/Content-Type、同源Cookie/no-store、单次超时、401清本地证明、互斥及test/typecheck/build。风险为提交成功但网络响应丢失；保留原Key/版本，不自动以新Key重做。回滚撤新方法/测试，无数据迁移。

实现：`postAdminUserState`只接受规范非零UUID、`enable|disable`、正整数安全版本`"vN"`和16～128可打印ASCII原幂等Key。Session内存CSRF不暴露给调用方；请求不带body或Content-Type。401清本地证明，其他响应由下一独立DTO客户端解释。自停用的历史重放200不能证明当前新Session已撤销，因此传输层不盲清身份。

验证：新增6测试，前端271/271、typecheck、Vite build通过。未本项运行真实HTTP/PG、实际浏览器或正式信任/TLS；状态DTO/UI、50+分页和Gate3/可用包仍待。兼容0049，无API/Schema/Migration/权限/依赖变化。
