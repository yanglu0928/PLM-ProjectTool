# SUR-01-A06-A01：Survey 前端与交互前置核查

日期：2026-10-06。结论：`SUR_01_A06_A01_FRONTEND_PRECHECK_PASS`。下一项：`SUR-01-A06-A02` Survey 四读严格前端客户端。

## 核查结论

1. Survey 定义十个冻结 Operation 已完成 Windows 11 生产 HTTP/PostgreSQL 组合，但前端没有 Survey 模块、客户端、路由、页面或项目入口；不能以 Excel、聊天输出、Handover 页面或 AI 建议页代替正式调研定义视图。
2. Version GET 已返回完整问题、选项、条件、预期输出、是否必答/需证据、目标部门和四类类型化固定来源，足以先构建只读问题卡片；列表不得把摘要或当前正式版引用误作完整 Version。
3. 用户确认的交互原则继续生效：实际面对面调研记录优先，业务表单/TEMPLATE只作参考；页面不得把模板问题、AI建议、MANUAL说明或未批准来源描述成客户事实。需要人工维护时必须明确字段、格式、示例、来源和为何需要维护，不能只给空白输入框。
4. 当前来源投影不能安全完成所有来源的“一键定位”：TEMPLATE含公开Document/Version标识，可导航至受权文档历史；Handover/Capability使用版本内row identity，不能由浏览器猜成公共Item ID；MANUAL只有说明，没有Document/Evidence locator。前端不得展示内部UUID按钮后宣称已定位，也不得复制跨模块正文。

## 交互与安全边界

- Survey列表只显示名称、状态、当前批准Version引用和更新时间；Version详情按用户动作分层读取，两个opaque cursor只保留在组件内存，不写入URL、localStorage或日志。
- 每个问题以卡片显示主题、问题、目的、预期输出、题型、是否必答/需证据、选项和可理解的条件摘要；原始`validation_rule`/`condition_rule`只允许严格已知V1形状，未知结构失败关闭，不把任意JSON直接渲染为可信说明。
- 来源按`HANDOVER_ITEM/CAPABILITY_ITEM/TEMPLATE_DOCUMENT_VERSION/MANUAL`明确标记，并区分“项目实际记录/已批准交接事实”“标准能力参考”“模板参考”“人工来源说明”。TEMPLATE必须持续显示“仅供问题结构参考，不是客户事实”。
- 可安全导航的TEMPLATE只链接到当前Project受权Document Owner页面；Handover/Capability/MANUAL在来源解析Owner完成前显示“尚无受控定位入口”，不拼接内部路由。后续解析入口必须由服务器重验当前Project权限、固定版本与最终可见目标，按点击返回最小导航/locator，不返回存储路径或整段正文。
- 写操作继续采用Session私有CSRF、强ETag、原幂等Key、显式二次确认和未知结果保护。A02仅实现未接页面的四读客户端，不创建、修改、归档、校验或送审。

## 后续拆分

- `A02`：四读严格前端客户端，固定Envelope/DTO、父资源绑定、零基问题序号、类型化来源、目标部门、ETag和两类品牌cursor。
- `A03`：Survey列表/详情/Version问题卡片与项目导航；先提供TEMPLATE受权导航及其他来源的真实可用性提示，不伪造定位。
- `A04`：登记兼容API增量并实现Survey来源只读解析Owner/HTTP；Handover/Capability解析为公共业务引用，MANUAL只有绑定Evidence/Document事实时才返回定位，否则明确不可定位。
- `A05`：接通按需来源定位并做Windows真实浏览器/PG只读闭环。
- 后续独立任务：定义创建/修改/归档、Version编辑/校验/送审安全交互；Round/Assignment/Response/Conclusion及Workflow资格按各自Owner实施，不混入本轮定义读取。

## 影响与验证

本项为静态前置核查，无程序、Schema、Migration、冻结API、依赖、配置、Secret、网络或客户数据变化。已交叉核对冻结API-04、Survey读写/送审增量、A07生产组合、Handover/Evidence/Document现有前端和项目导航。结论不代表前端、来源解析、真实浏览器、Round/Response/Conclusion、正式信任、Gate 3、UAT或发行通过。
