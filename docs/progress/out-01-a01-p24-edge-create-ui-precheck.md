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
