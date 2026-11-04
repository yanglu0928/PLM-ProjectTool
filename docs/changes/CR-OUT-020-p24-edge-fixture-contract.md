# CR-OUT-020：P24 Edge 合成版本 fixture 解析失败修正

- 日期：2026-11-04
- 状态：P24 PASS_SCOPE_LIMITED；GitHub hosted run 41888874127 14/14 jobs成功
- 来源：OUT-01-A01-P24 首次 hosted run 41875807078
- 基线：冻结Requirement Read Contract、CR-OUT-019、P24编码前检查
- 影响面：仅validation harness与云端验收证据；无产品代码、API、Schema或Migration变化

## 观察到的偏差

P24 Edge浏览器成功完成合成登录，并请求了项目Requirement及Version列表；页面显示“暂时无法读取项目需求”，因此没有走到请求按钮或POST步骤。首次失败日志没有记录响应状态和被解析对象的字段集合，当前不能断言是具体哪个字段导致拒绝，也不能把它归因于产品逻辑缺陷。

## 修正决定（实施前）

将测试数据构造改为按冻结Summary字段逐项显式组装，避免从Detail对象散播字段；为P24本地合成服务器记录每个API响应的HTTP状态与安全字段形状（不记录Cookie、CSRF、幂等Key或敏感正文）。失败报告仅保留必要诊断。重新执行 hosted Edge、前后端回归、父包/A17/A34/A35/A50全链。

不改RequirementReadClient或业务页面，不放宽解析器，不接入真实信任源，不生成DOCX。

## 风险、回滚与验收

- 风险：修复 fixture 后若仍有拒绝，需依据新状态/字段诊断继续定位；不得以放宽生产解析规则绕过。
- 回滚：撤销P24 harness内的fixture/诊断改动与对应专用job。
- 验收：Edge加载批准版本详情、精确POST payload和CSRF/Idempotency、受理/历史导航、合成SYSTEM_UNAVAILABLE失败关闭且无自动重试、未批准版本隐藏入口；合成数据且external API=0。


## 修正已实施（2026-11-04）

测试harness已将RequirementVersion Summary改为显式字段对象，并为失败日志增加HTTP状态/字段存在性记录；不记录Cookie、CSRF值、幂等Key或请求正文。产品解析器和业务组件未修改。通过GitHub hosted全链工作流重新验证，结果待回填。


## 根因进一步定位（实施前记录，2026-11-04）

对照RequirementReadClient后确认：合成项目需求响应只返回JSON正文中的etag字段，遗漏了真实GET合同要求的HTTP ETag响应头；客户端明确要求该响应头与正文etag相等，因此拒绝详情。该为P24合成HTTP fixture缺少冻结合同头字段，不是产品读取逻辑缺陷。此前已实施的Summary显式字段修正保留为防御性fixture对齐；下一步仅给合成Root GET补齐匹配的ETag header，然后重跑Hosted全链。


## ETag fixture 修正（2026-11-04）

已在P24合成HTTP服务中为Requirement GET响应附加与JSON正文etag相同的HTTP ETag。显式Summary对象和去敏HTTP状态诊断一并保留。未改产品逻辑。下一步依赖GitHub hosted Edge及完整流水线复验。


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


## Retry assertion 校准已实施

Edge harness不再要求错误后手动重试按钮消失；保留对role=alert服务不可用提示的断言，并在500ms窗口确认没有自动发出第二个POST。只改验收harness，产品实现未改。


## 未批准版本场景的测试路由断言偏差（修复前登记，2026-11-05）

- Run 41887798979已通过P24请求受理和模拟SYSTEM_UNAVAILABLE 503路径，验证正确CSRF/幂等/固定负载、可见错误提示及500ms内没有自动重发。随后测试未批准版本时超时。
- 根因：公共 `openRequirement()` helper无条件等待 `#output-create-title`，但未批准版本的正确产品行为是根本不渲染Output Create区域，所以helper在进入负向断言前等待了不存在的元素。
- 修正：给helper增加是否预期创建区域的参数；未批准场景等待需求详情加载/固定版本状态后直接断言请求按钮与创建区域均不存在。仅调整浏览器验收脚本，不改产品组件。


## 未批准版本 helper 修正已实施

openRequirement helper增加 expectCreateAction 参数。已批准场景等待创建区域出现；未批准场景等待固定版本详情正文并断言整个操作区域和请求按钮不存在。未更改产品逻辑。

## 最终 hosted 验收（2026-11-05）

- GitHub Actions [run 41888874127](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41888874127) 完成，14/14 jobs success。GitHub hosted Windows Server 2025 runner使用D盘runner temp，下载同run前端production build并以Microsoft Edge headless完成验收。
- Frontend：204/204 test files、2,093/2,093 tests、typecheck与production build通过。Backend：4,022 tests与wheel通过。PG18/pgvector、父包/清洁解包以及A17/A34/A35/A50均成功。
- Edge专项检查：已批准固定版本显示请求入口；提交的template/policy/operation/source refs精确，CSRF与单一Idempotency-Key存在；HTTP 202回执显示并导航到历史；模拟503错误可见且500ms观察期间没有自动第二次POST；未批准版本没有请求操作。专项合成POST共2次（一次202、一次受控503）。
- 合成用户、项目、需求版本和API；customer_data=false、external_api_calls=0、plugin_executed=false、docx_generated=false。P24只验证UI合同与浏览器状态，不代表真实Publisher信任、文件生成、Windows 11实机、Gate、Pilot或Release。
- 发现并修复的产品缺陷及所有harness/fixture/断言偏差均已按发生顺序保留在本CR中；hosted成功后才关闭该WBS。
- 结果文档：docs/progress/out-01-a01-p24-edge-create-ui-result.md。
