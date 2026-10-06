# SUR-01-A06-A02：Survey 四读严格前端客户端

日期：2026-10-06。结论：`SUR_01_A06_A02_FRONTEND_READ_PASS`。下一项：`SUR-01-A06-A03` Survey 列表、Version 与问题卡片页面。

## 实施结果

新增未接页面的 `SurveyReadClient`，覆盖 Survey LIST/GET 和 Version LIST/GET 四个冻结 GET。请求固定 same-origin、`no-store`、拒绝重定向、JSON Accept 和 10 秒有界超时；Project/Survey/Version ID、1～200页长和opaque cursor在发网前校验。Survey与Version cursor采用不同TypeScript品牌，不在浏览器解码、生成或持久化。

客户端对白名单Envelope/DTO、父级Project/Survey/Version绑定、Survey强ETag、UTC时间、状态、计数、排序和分页执行失败关闭校验。Version完整投影要求问题从零连续编号，Option/Source/目标部门按零基ordinal连续，声明计数与实际集合一致，身份不重复；读取客户端不把列表结果、Review引用或正式Version引用当当前审批证明。

问题定义严格接受六种题型和V1有界validation/condition规则；条件树限制深度、分支、叶子、operator和值集合，嵌套数组/对象深冻结，非法日期、重复IN值、未知字段和非有限数值拒绝。四类来源必须满足互斥类型化形状；MANUAL只保留规范说明，TEMPLATE/Handover/Capability只保留固定标识，不读取路径、正文或猜测导航。

## 客观验证

- 定向25项通过：四条路径、两类cursor透传、父级绑定、强ETag、零基问题/ordinal、四类来源形状、V1规则、深冻结、声明计数、稳定排序/重复、非法ID/页长、错误映射、Envelope/Content-Type和超时。
- 前端全量79个文件、1,420项通过；TypeScript typecheck通过；Vite production build转换164个模块并成功产出。
- Vite主JS为`599.01 kB`，继续触发现有500 kB分块提示；本项未接页面且未增加静态路由导入，警告保留给发行性能任务，不将构建成功外推为加载性能通过。

## 兼容、回滚与未关闭项

纯前端新增且尚未接路由/页面；无Schema、Migration、后端API、依赖、配置、Secret、网络外发或客户数据变化。删除未引用客户端即可回滚。

A03页面、来源解析Owner/按需定位、写操作客户端与页面、真实浏览器/PostgreSQL、Round/Response/Conclusion、正式key/信任、Gate 3、UAT及发行仍未完成。
