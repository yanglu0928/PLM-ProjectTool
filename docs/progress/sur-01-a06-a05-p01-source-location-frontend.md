# SUR-01-A06-A05-P01：Survey 来源定位客户端与点击交互

日期：2026-10-06。结论：`SUR_01_A06_A05_P01_FRONTEND_PASS`。下一项：`SUR-01-A06-A05-P02` Windows 11真实浏览器来源定位闭环。

## 实现

- 新增严格`SurveySourceLocationClient`：校验固定Project/Survey/Version/question/ordinal路径、精确互斥JSON、Project scope、公共记录与location一致性、受控错误和超时。
- 问题卡片默认只显示来源种类和维护指引；用户点击后才由服务器重新验权并展开位置，不读取或猜测旧四读中的内部row identity。
- MANUAL提示补充访谈时间、参与人、结论及后续固定证据；GLOBAL不可展开、目标缺失、历史但非当前合格分别给出明确说明。
- PROJECT Template可打开固定Document原文；Handover跳转公共分析；Evidence必须再次调用既有Viewer核验locator、完整性和权限后才显示精确位置及原文链接。

## 验证

- 定向3文件39项通过：客户端严格投影/错误/超时，问题卡片人工、Document、Handover、Evidence点击链，以及原有Survey读取。
- 前端全量82文件1438项通过；TypeScript通过；Vite生产构建172模块通过。
- 生产构建主JS 636.34 kB、gzip 159.18 kB，仍有大于500 kB分块提示；这是延续既有偏差，不影响本项功能通过，后续需动态拆包。

## 影响与剩余项

无后端、Schema/Migration、角色、依赖、配置、Secret、网络或外发变化；删除新增客户端和结果区即可回滚，后端location仍可独立使用。P02真实浏览器、定义写UI、Round/Response/Conclusion、Gate 3/UAT及发行仍未通过。
