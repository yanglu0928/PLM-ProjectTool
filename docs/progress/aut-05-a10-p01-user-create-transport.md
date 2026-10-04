# AUT-05-A10-P01 管理员用户创建受控传输

2026-09-28 / 0.1.0.dev0 / PASS（前端Auth固定路径传输合同）。

编码前检查：Phase2/Gate2批准；输入冻结API-02 `AUTH_USER_CREATE`、CR-AUT-005及后端Windows显式写模式P05，原`SessionClient`私有CSRF桥接。仅Auth前端写传输，无实体/Schema/后端API/权限/依赖变更。DEC-413先记录风险/回滚；撤新增方法/测试即可，无迁移。验收同源Cookie/私有CSRF/原Key/16KiB/互斥/401清状态/超时单次及前端全量测试构建。

实现：只扩固定`POST /api/v1/admin/users`，不提供任意URL、CSRF getter或密码持久化；两固定路径共用原请求纪律。503或网络/超时不丢同账户原会话、不自行重试；401清内存身份及CSRF。调用方负责原正文/原Key恢复，服务端每次仍重核Admin/License。`SessionClient`序列化不暴露密码/Token。

验证：新增7参数化场景，前端219/219、typecheck、Vite build通过；覆盖请求头/路径/正文、只读零写、大小、401/503、跨命令互斥、超时。未接User DTO或页面，未本项跑真实HTTP/PG/浏览器、后端全量/性能。兼容既有0049，不升级。下一P02 User创建安全客户端与原密码重输/同Key语义；正式trust/HTTPS/CR008性能FAIL/Gate3/可用包仍待。
