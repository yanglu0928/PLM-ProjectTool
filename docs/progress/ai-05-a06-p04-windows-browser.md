# AI-05-A06-P04 Windows 11 AI Task 三步提交真实浏览器验收

日期：2026-10-04；状态：`WINDOWS_BROWSER_PASS`；依据冻结 API-03、CR-AI-021、DEC-782～785 与 P01～P03。下一项：`AI-05-A07` Windows 11真实浏览器/隔离PG完整AI工作台验收。

## 编码前与环境

- Windows 11 x86-64，build 26200；Microsoft Edge 154.0.4258.53；PostgreSQL 18.6，端口55434。
- 实际Vite生产构建产物通过同源本地预览代理连接生产FastAPI组合；数据库、登录账户、项目、文档、Provider/Model/Prompt/策略均为一次性合成对象。
- Provider执行地址固定为不可解析的`.invalid`域；验收只创建PENDING Job，不运行Worker，数据库最终0 Invocation、0 Provider I/O。
- 托管浏览器控制内核两次初始化均因运行资产路径缺失而失败。按持续授权记录偏差，改用本机Edge的DevTools Protocol驱动同一实际页面；未改产品代码或降低验收断言。

## 结果与发现

首轮真实Edge在进入提交页后，文档列表请求200，但Options未发出即显示不确定结果。浏览器异常栈证明`AISubmissionClient.options`以`this.fetcher(...)`调用原生`Window.fetch`，Edge按Web IDL拒绝错误接收器并抛出`Illegal invocation`。原jsdom mock不检查接收器，因此此前测试未发现。

已将Options transport改为局部函数的无接收器调用，并新增一个严格测试：只要transport收到类实例接收器就抛出同类错误。修复后完整浏览器路径通过：

1. 合成项目经理登录；进入授权项目、AI工作台和新建分析任务。
2. Options只显示受控Task/Egress/Route；选择有效固定DocumentVersion，生成Preview，不产生Invocation或Provider调用。
3. 页面显示region、来源、字节/Token/重试上限、风险和到期时间；勾选本轮明确同意后单独Authorize。
4. 再次单独创建Task；页面显示Task/Job身份，无告警。

数据库终检精确为1个Preview、1个AUTHORIZED Authorization、1个QUEUED AI Task、1个PENDING Job、0 Invocation。临时前后端、Edge profile、数据库、数据库角色、Windows Vault凭据和文件根均已清理。Options、Preview、Authorization、Created四张全页截图完成视觉检查，未发现截断、重叠、错误状态或敏感正文。

## 回归与产物

- `AISubmissionClient`定向7项；前端全量67文件/1250项通过。
- `vue-tsc`/`tsc`通过；Vite生产构建145模块通过。
- dist SHA-256：HTML `bd70f12e03232c0026b5aecfdcf85eea62da3c5b87c8fac6b1ebb352aded5892`；JS `56e16486ec09ceee977e6a8d782508612ea1e29328dddf238318dafbc18a204d`；CSS `b4aa05c9062e66efffb9a02d95c185d6861977aa595c6573ad56727b5f1b9917`。
- 验证标记：`AI_05_A06_P04_WINDOWS_BROWSER_PASS`、`AI_05_A06_P04_WINDOWS_BROWSER_CLEANUP_PASS`。

本项不证明真实Provider执行、Suggestion接受/拒绝、Server 2025、Debian 13、Gate 3、UAT或发行包。AI-05-A07继续验证创建后工作台列表、Task详情/Invocation/Job导航和当前授权读链；Accept/Reject仍须绑定真实目标Draft Owner与Review锁，不在本项伪造。
