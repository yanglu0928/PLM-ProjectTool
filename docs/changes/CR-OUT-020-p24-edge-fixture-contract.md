# CR-OUT-020：P24 Edge 合成版本 fixture 解析失败修正

- 日期：2026-11-04
- 状态：偏差已记录；fixture修正与hosted全链复验待执行
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
