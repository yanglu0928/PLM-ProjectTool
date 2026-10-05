# HND-02-A05-A05-P02：Action 写操作工作台

日期：2026-10-05。结论：`HND_02_A05_A05_P02_ACTION_WRITE_WORKBENCH_PASS`。下一项：`HND-02-A05-A06` Windows 11 真实浏览器闭环。

## 完成范围

- 项目经理与实施成员可从人工调研记录或固定 Analysis Item 创建待办；登记页明确提示“登记不等于确认分析结论”，并用字段名称、必填、格式、示例组成可增删的人工维护规格。
- 待办详情按会话角色、assigned owner 与当前状态给出 PATCH、START、SUBMIT、VERIFY、CANCEL 操作入口。前端判断只控制操作提示，后端仍重新检查授权、版本、Evidence 与 License。
- PATCH 可维护标题、负责人、期限、优先级和完整输入字段规格；SUBMIT 明确要求 Document/固定Version配对及 Evidence；VERIFY 要求 Evidence；全部状态操作要求可审计理由。
- 每次已解析成功的写回执后重新 GET 当前 Action，再显示当前状态；首次幂等回执不直接当成当前事实。网络结果不确定时只提供“使用原操作号和版本重试”，不自动换 Key/ETag。
- `SUBMITTED`、`VERIFIED`、`CLOSED` 继续分离；生产组合尚缺真实 Survey/Requirement Resolution Owner，故 VERIFIED 页面展示 CR-HND-008 原因并禁用 CLOSE，未提供绕过入口。

## 验证

- 页面专项 7 项通过：只读保护、SUBMITTED 语义、Evidence 按需定位、人工来源引导、START 后 GET 刷新、未知结果原 Key/ETag 重试、CLOSE 失败关闭提示。
- 前端全量 75 个测试文件、1339 项全部通过；TypeScript/Vue 类型检查和 Vite 161 模块生产构建通过。
- 主 JavaScript 为 564.57 kB（gzip 142.14 kB），超过 500 kB 的拆包警告继续作为发行性能项；A06 前不虚报真实浏览器可用。

## 兼容、回滚与未关闭项

无 Schema、Migration、后端 API、依赖、配置、Secret、网络或外发变化。撤页面写区可恢复只读工作台，数据库历史不变。

当前冻结 API 只有 UUID 引用，没有项目成员、DocumentVersion 或 Evidence 选择器合同，因此界面以明确标签录入引用，未伪造名称搜索能力；后续若引入选择器须使用对应 Owner 的受权只读合同。A06 将用 Windows 11 真实浏览器与 PostgreSQL 18 验证可用链，CLOSE 正例仍等待 CR-HND-008 的真实 Owner。
