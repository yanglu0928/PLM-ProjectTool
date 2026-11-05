# CR-OUT-032：OutputArtifact 用户检索与下载关联

- 日期：2026-11-06
- 阶段/WBS：Phase 2 Platform Core / OUT-01-A01-P35 → P36
- 状态：P35 PASS_WITH_LIMITATION；P36代码候选已准备提交，GitHub hosted验收待完成
- 来源：CR-EXEC-002优先形成Windows 11受控内部Pilot；P34B已证明内部生成文件发布，而用户侧无法从OutputRequest定位Artifact。
- 基线：冻结 API Contract V1 的 OUTPUT_REQUEST_GET/LIST、OUT-02、Document/DocumentVersion/Storage合同，CR-OUT-028/031；P34B PASS_SCOPE_LIMITED。

## 证据与问题

OutputRequest固定读投影仅返回状态及请求/Job/Execution等引用；输出历史UI只有状态且提示不代表可下载。P34B验证内部Storage与数据库发布链，没有产品HTTP/Worker启动。Document已有项目授权的元数据/版本读取以及完整性复核内容下载服务，但未提供从OutputRequest到Artifact/DocumentVersion的安全关联入口。两组opt-in router存在不能当作Windows服务已挂载的证据。

## 方案比较与选择

- 方案A：在现有OutputRequest GET/LIST增加Artifact和DocumentVersion字段。实现直接，但改变冻结projection及要求精确字段匹配的前端合同，影响既有调用方。
- 方案B（选择）：新增独立的项目范围只读Artifact引用GET endpoint；原有GET/LIST响应保持不变。只有请求SUCCEEDED、唯一绑定Artifact为AVAILABLE且Project/Document/Version/FileObject/Hash/size/MIME关系一致时，返回固定Document/Version身份和受控内容route。字节仍经既有Document下载service读取。
- 方案C：前端枚举项目全部Document并猜哪个文件属于请求。无法证明归属且会有歧义，拒绝。

## 实施边界

- 不增表/字段/Migration，不改既有API response、Output状态Owner、生成Worker、Storage或TraceLink基线。
- 新route只投影固定Artifact、DocumentVersion身份及必要元数据；不得返回Storage locator、Secret或生成正文。
- 查询同时限定 ProjectId + OutputRequestId；在项目读取授权事务内验证Artifact AVAILABLE、Document GENERATED_ARTIFACT、Version/FileObject AVAILABLE及精确关联。缺失/冲突/不可用均失败关闭。
- 使用受保护Document content endpoint；内容Hash与大小由既有下载服务验证。前端仅在请求SUCCEEDED且新接口返回合同完整引用时提供下载。
- 新route沿现有Windows Output read opt-in composition扩展；不宣称默认服务已挂载。若Pilot composition缺Document Download router，另行记录装配任务，不回退为直读文件。

## 风险、迁移与回滚

风险为Artifact与Project边界漂移、非AVAILABLE文件过早可见、或projection漏做权限复核。以复合SQL关系、项目读取授权、AVAILABLE过滤、Document下载二次授权与Hash/大小复核控制。
无Schema/API迁移。回滚移除新增route/service/Repository及前端入口；不删除Artifact/Document/DocumentVersion，不改变已发布历史。

## 验证计划

GitHub hosted Windows Server 2025 D: + 临时 PostgreSQL 18 + 纯合成数据。增加Application/Repository/HTTP权限/异常测试、PG18真实projection断言；前端严格解析、SUCCEEDED下载按钮、其他状态无入口和下载触发测试；后端全量/wheel、前端全量/build。随后运行可独立成功的父包/A17/A34/A35/A50。P25 initdb诊断继续暂停，不能阻止本项，也不能将整体workflow称为全绿。

## P36 Hosted前静态复核偏差（2026-11-06，修复前记录）

新增PG18 verifier helper放置在连字符目录，但P33 smoke verifier用Python模块导入时采用了下划线路径，二者不匹配，预计会在验证器导入阶段失败。此偏差只影响测试接线，不改变产品逻辑或验收范围。修复：将helper移动至名称匹配的下划线目录并统一import，再运行新Hosted全链。

修复已实施：helper改放到可导入的下划线目录，P33 verifier更新为同一路径的绝对包导入。等新的Hosted run确认，无产品逻辑改动。

## 首轮 P36 Hosted 验收偏差（run 42118811778，修复前记录）

Hosted Backend运行4,087项测试，其中2项P36新增测试失败：

1. Repository SQL参数集合断言把两个数据库列之间的输出类型等值比较误计为DOCX bind参数；产品查询使用受控列关系，测试错误多期待一个字面参数。
2. Windows组合测试检查APIRouter.include_router前的包装路由对象.path；当前FastAPI包装对象此时path为None，route需在FastAPI app实际include后检查。

前端测试/build、PG18 sidecar重建、A17 harness syntax通过。后端失败导致wheel及后继PG18父包/A17/A34作业跳过。本轮P36不通过，尚无真实Repository PG18验证结论。修复范围仅为测试期望与检查位置，产品实现不改，随后重新运行完整Hosted workflow。

修复执行：只改两项测试。删除多余的DOCX字面bind期待；组合路由测试改在APIRouter被FastAPI接纳后检查最终path。没有改产品查询/权限代码；待Hosted全链复验。

## 第二轮 P36 Hosted 测试夹具偏差（run 42119917628，修复前记录）

Backend 4,087项中仅 test_factory_wires_request_and_artifact_routes 失败。测试在 FastAPI include_router 后直接遍历 app.routes，当前FastAPI版本仍以延迟组合对象保存路由，因此path字段为None；其余Application、SQL projection、HTTP及前端检查通过。后端失败使wheel及依赖它的父包/PG18 verifier步骤跳过，故真实Repository PG18查询尚未执行。修复：对最终 app.openapi()['paths']断言两个路由。产品代码不改，完成后再次全Hosted验证。

第二轮测试夹具已修正：Windows composition测试现在检查最终FastAPI OpenAPI paths字典，兼容当前版本的延迟router包装。没有变更产品路由或接线。

## P36最终关闭（2026-11-06）

P36按范围PASS_SCOPE_LIMITED，最终证据及限制见docs/progress/out-01-a01-p36-artifact-reference-read-result.md。真实PG18 Repository断言、4,087后端测试/wheel、前端/build、父包PG18 smoke、A17/A34/A35/P24/A50全部通过。整体run 42121003242因独立P25失败而非全绿；正式Platform trust与前端用户下载入口仍未完成。下一项OUT-01-A01-P37。


## P37 前端实现候选（2026-11-06）

已新增输出Artifact引用同源Client、SUCCEEDED状态下载入口及加载/安全错误提示；在导航前验证固定项目、请求、文档版本及内容route。仅改前端，无后端/API/Schema变化。正式Platform trust仍未建立；用户侧真实下载未验证。

## P37 首轮 Hosted 前端解析偏差（run 42124943609，修复前记录）

GitHub hosted 前端全量测试中，`OutputRequestListView.spec.ts:99` 无法转换：对象字面量后换行再写 `as unknown as OutputRequestListClient`，转换器报告“Expected a semicolon…”。全量统计为 2,092 tests passed、1 个 suite failed；该suite未执行，typecheck/build因测试失败跳过。此为新测试夹具的类型断言换行语法错误，不是产品运行断言失败；P37不能通过。修复方案限于将对象断言包入括号或合并为合法表达式，不改产品逻辑、API或验收范围；之后完整Hosted重跑。
