# HND-02-A05-A02：Handover Action CREATE/PATCH 严格 HTTP

日期：2026-10-05。结论：`HND_02_A05_A02_ACTION_CREATE_PATCH_HTTP_PASS`。下一项：`HND-02-A05-A03` Action 五个生命周期写 HTTP。

## 实施结果

新增默认关闭的 Action CREATE/PATCH Router，并在通用应用工厂增加独立可选注入点。未注入时两个路径保持 404；显式注入后，CREATE 返回 201、Location、强 ETag 与 OPEN 最小事实，PATCH 返回 200、强 ETag 与允许的元数据事实。

传输层复用既有严格 JSON、安全会话和并发头解析，只接受 canonical UUID、canonical UTC `Z` 时间、白名单正文、受限大小 JSON、受信 Origin、Session 与 CSRF。CREATE 强制 `Idempotency-Key`，PATCH 强制 `If-Match` 且只接受非空部分字段；角色、当前项目、受理人、来源、期限、状态、License、Audit、持久收据和事务仍由既有 Owner 决定。

错误投影隐藏越权资源，把版本冲突、Action 状态冲突、项目归档、幂等冲突、License 与验证错误映射到冻结公共错误，不返回内部异常或数据库细节。

## 客观验证

- 新增合同测试3项；默认关闭、成功回执、安全头、缺幂等/If-Match、空/未知字段、非UTC时间、非canonical UUID及稳定错误投影通过。
- Handover合同与Action单元定向54项通过。
- 后端全量2709项通过、3项跳过。
- Windows Python 3.13 wheel构建与wheel内导入通过；SHA-256 `e8a6e5bb84cac252613c3feeb9eb2553f16bc1108d08e0a87638c4a111fb1b97`。

## 兼容、回滚与未关闭项

无Schema、Migration、冻结URL、依赖、配置、Secret、网络、外发或客户数据变化。撤应用工厂可选注入和Router即可恢复404，合法业务历史不变。当前尚未在Windows生产组合挂载，因此此结论不代表真实PG写链或可用UI；五个生命周期HTTP、Windows真实组合、前端写操作、浏览器、正式信任、Server 2025、Gate 3、UAT与发行继续开放。
