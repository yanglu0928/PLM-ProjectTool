# OUT-01-A01-P24 编码前检查：DOCX 请求入口 Edge 集成

日期：2026-11-05  
状态：PASS_WITH_LIMITATION（范围与前置检查完成，尚未编码）

## 编码前检查

- 当前 Phase：Phase 2 Platform Core
- 当前 WBS：OUT-01-A01-P24
- 输入基线：冻结 API Contract V1 的 OUTPUT_REQUEST_CREATE；CR-OUT-019/P23 已限界完成；现有 RequirementVersion详情与 Output Create Action；CR-EXEC-002 Windows 11 Pilot顺序。
- 前置任务：P19显式Windows写组合及缺Publisher失败关闭已由run 41830014604验证；P22列表UI由run 41859511797验证；P23请求入口由run 41869866457验证。
- 涉及模块：前端 Requirement详情、Output Create Action、SessionClient和现有 Edge hosted browser harness。
- 涉及实体：合成 Project、批准 RequirementVersion、OutputRequest 请求/历史链接；不写真实业务数据。
- 涉及API：仅测试拦截的冻结 POST /api/v1/output/requests 与历史列表导航；Browser mock不得冒充真实API/生产信任。
- 涉及权限：合成已授权 PM 与不满足角色/版本的可见性；真实Session/License仍由既有后端负责，本项不重验。
- 验收标准：Hosted Edge打开真实production build的需求详情页；批准版本显示请求操作；验证固定template/policy/operation/source version与CSRF/Idempotency headers；模拟受理后状态文案及历史导航；模拟Publisher不可信拒绝时用户看到安全提示、无自动换Key重试；不批准版本不显示提交操作；全程无客户数据、真实插件执行或文件生成；浏览器记录可供审阅。
- 风险：合成API的成功响应易被误读为后端/生成通过。通过结果记录明确标注mock，只验浏览器契约，不提升Gate/Pilot/Release结论。
- 回滚：删除P24专用Edge脚本、合成HTTP服务/fixtures及workflow调用；不更改业务代码或默认路由。
- 执行环境：只允许GitHub hosted Windows runner的D: runner temp / 云端沙箱；禁止用户本机/C盘运行项目代码或测试。

## 实施步骤与候选文件

1. 检查现有 requirement detail route、Output Create Action以及已有Windows Edge harness。
2. 新建P24专用合成测试服务/浏览器脚本，不改产品代码。
3. 将单项Edge步骤接入 .github/workflows/cloud-sandbox-validation.yml，固定D: runner temp并输出去敏化JSON结果。
4. Hosted workflow失败先记录偏差，修正后全链复验。
5. Secret检查、结果文档、STATUS/CHANGELOG更新并提交到当前feature分支。

预期文件：validation/out-01-a01-p24-edge-create-ui/README.md、serve.py、run-edge-browser.mjs、workflow和P24结果文档。无Migration、API Contract或产品运行时变化。

## 编码前置记录

本检查与P23最终结果记录先提交到仓库。确认远端HEAD仍为本轮检查到的提交后，再开始P24 harness。

## 首轮 hosted 偏差（修复前登记，2026-11-04）

- Run [41875807078](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41875807078) 的P24 Edge job失败：合成登录后浏览器请求了需求详情与版本列表，页面进入“暂时无法读取项目需求”，未到请求提交步骤。前端、后端和A50专项通过；全链其他打包作业仍在收尾，整体run暂不关闭。
- 初始复核显示hosted合成版本响应与冻结 `RequirementReadClient` 解析契约不匹配；具体拒绝字段尚未从首次日志确定，不归因于产品缺陷或安全绕过。
- 修复前方案：把合成列表对象改成仅含冻结summary字段的显式结构，增加API响应状态/响应形状安全诊断；用相同run Edge完整重验成功、Publisher失败关闭和未批准状态。只修复fixture/harness，不改产品逻辑。客户数据、外部API、真实插件、DOCX生成均不涉及。


## 首轮偏差及已实施修正

P24首轮hosted run 41875807078在合成登录后读取需求详情/版本列表时落入通用读取失败，未提交Output请求。具体拒绝字段未由首轮日志保存，因此未推定为产品缺陷。偏差、风险和修正计划预先登记于CR-OUT-020。随后将Summary fixture改为冻结解析器所要求的字段白名单，并加入仅记录HTTP状态/安全字段形状的诊断；不输出Session cookie、CSRF、幂等Key或客户正文，不改业务代码。完整重验待hosted run。


## 根因进一步定位（实施前记录，2026-11-04）

对照RequirementReadClient后确认：合成项目需求响应只返回JSON正文中的etag字段，遗漏了真实GET合同要求的HTTP ETag响应头；客户端明确要求该响应头与正文etag相等，因此拒绝详情。该为P24合成HTTP fixture缺少冻结合同头字段，不是产品读取逻辑缺陷。此前已实施的Summary显式字段修正保留为防御性fixture对齐；下一步仅给合成Root GET补齐匹配的ETag header，然后重跑Hosted全链。


## ETag fixture 修正已实施

合成Requirement GET现返回HTTP ETag，值与JSON正文etag完全一致，满足前端冻结RequirementReadClient合同。保留先前显式Summary和去敏诊断。产品API/解析器没有修改；Hosted复验等待中。


## 第二轮 hosted 偏差（修复前登记，2026-11-04）

- ETag修复后的 run 41878499626 已成功读取批准版本并到达唯一POST；日志确认POST返回202、CSRF与幂等头存在。Edge等待成功回执UI状态时超时，截图未显示回执文案；测试未通过。
- 新证据排除了版本读取和请求未送达问题；具体是输出Create组件状态、响应解析还是浏览器可访问性树观察尚待隔离。不得改产品文案/业务逻辑或宣称提交成功路径已通过。
- 修复前计划：在 harness 安全诊断中补充 `.output-create` 是否存在、role=status/alert文案和按钮名快照；只输出合成UI文本，不输出请求正文、CSRF、Cookie或幂等Key。对照 OutputRequestCreateClient 的严格202收据解析与 Vue 状态流，再以 hosted Edge重验。产品代码不改。


## 回执UI诊断已实施

P24失败快照现记录输出操作区域文本、role=status/alert及可见按钮标签，并继续排除Cookie、CSRF、幂等Key和请求正文。该诊断用于区分后端mock响应、OutputRequestCreateClient解析与Vue状态呈现，不调整产品逻辑。Hosted复验待完成。


## 第三轮 hosted 偏差与产品根因（修复前登记，2026-11-05）

- Hosted run 41882240312 已完成合成认证、当前批准版本读取，并对固定输出路径提交一次HTTP 202；CSRF与幂等头存在、请求负载符合预期，但界面未显示请求回执，P24失败。
- 对照源码确认真实产品原因：`SessionClient.#postCommand` 在请求进行中把 `canSubmit` 置为false；`OutputRequestCreateAction.vue` 又用包含 `session.canSubmit` 的 `canCreate()` 作为整个 `<section>` 的条件。按钮点击后组件因此卸载，异步结果因mounted检查被丢弃。Edge证据与单测未覆盖该真实状态交互。
- 实施前修正方案：拆分只决定操作区可见性的 `canRender()` 与提交可用性的 `canSubmit()`；区域在受控请求进行中保持挂载，按钮在busy/SessionClient busy时禁用。增加真实SessionClient+待完成POST的前端定向测试，并由P24 Edge复验202回执、503安全错误、幂等不重试与未批准版本隐藏。无API/Schema/Migration改动。
- 风险/回滚：请求期间必须仍尊重项目/角色/当前批准版本；props变化仍取消旧代次结果。回滚为恢复原组件门控和删除该测试。仅影响批准版本Output请求交互。


## 产品缺陷修复已实施（2026-11-05）

按CR-OUT-020将版本/角色/授权决定的区域显示资格（canRender）与SessionClient可提交资格分开。写请求忙时操作区保持挂载，按钮禁用；SessionClient返回后可显示回执/错误。新增真实SessionClient异步POST定向用例，覆盖忙态期间组件仍挂载和202收据展示。当前只完成源码实施；hosted full run未过前不得关闭P24。


## 定向测试夹具偏差（修复前登记，2026-11-05）

- 产品门控拆分提交后，hosted run 41883970738 前端测试为2,092/2,093通过；唯一失败是新增用例引用当前测试文件未定义的 `response` helper，ReferenceError发生于测试构造Session阶段。产品缺陷验证未执行，P24 Edge因依赖前端job而跳过。
- 修正：在用例内显式创建synthetic login及202 Response，不增加不必要的全局helper；保留真实SessionClient忙态、区域保持挂载和回执展示断言。只修纯测试夹具，产品代码不改。之后重跑hosted全链。


## 测试夹具修正已实施

新增测试现显式构造包含 data/trace_id 的合成登录Response；pending POST仍返回严格的HTTP 202 Output receipt。只改测试夹具，不改产品代码。等待GitHub hosted验证。


## 第二次定向测试夹具偏差（修复前登记，2026-11-05）

- Run 41884900898 的前端回归仍为2,092/2,093通过；新增pending POST测试中的合成Response引用了未定义的 `trace` 常量，ReferenceError发生在构造响应阶段。产品代码与前一项 canRender/canSubmit 修正未触发失败；P24 Edge因前端job失败被跳过。
- 修正：使用测试文件内已有的项目UUID作为合成trace_id，或在本测试内显式定义。仍只修纯测试数据构造，不更改业务逻辑；再次运行完整GitHub hosted链。


## Trace fixture 修正已实施

P24新增用例的trace_id现复用本测试文件已有的synthetic Project UUID；仅替换未定义测试常量，不改产品代码。待Hosted重新验证。


## Trace夹具修正未闭合（修复前登记，2026-11-05）

- Run 41885874291 新增用例仍失败，ReferenceError定位到202 Response的另一处 `trace` 引用；前一提交只替换了登录Response中的引用，漏掉回执Response。测试依旧2,092/2,093通过，P24 Edge跳过，产品逻辑未被判失败。
- 修正：在本测试内为所有Response统一使用已定义的项目UUID作为synthetic trace_id；提交前检查该测试代码无未定义trace符号，然后重跑 hosted 全链。


## Trace fixture 全量修正已实施

登录和202回执响应现在统一使用已定义的项目UUID作为synthetic trace_id；新增测试区块经静态文本检查没有剩余的裸trace变量。仅改测试fixture。


## P24 验收断言偏差（修复前登记，2026-11-05）

- Hosted run 41886767805 已通过前端全量测试并在Edge中验证受理回执、固定请求/CSRF/幂等以及历史路由；P24随后发送一次模拟SYSTEM_UNAVAILABLE 503并观察到错误。
- 失败断言错误地要求503后Create按钮消失（true !== false）。产品设计允许用户在明确已知的服务暂不可用后手动重试；预先批准的验收只要求不得自动重试。日志确认总POST仍为两次（首次202、一次模拟503）。
- 修正：移除“按钮必须消失”断言；在错误提示可见后等待短暂窗口，断言POST总数仍为2且保留历史入口。测试人工重试能力不作肯定/否定结论；不改产品代码。
