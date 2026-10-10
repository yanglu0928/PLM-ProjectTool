# PRT-01-A10-A07 Windows 11 Edge / PostgreSQL 18

`serve.py` 复用既有隔离浏览器基座，只增加合成的当前批准 RequirementVersion 与两条验收标准；生产写组合仍逐请求验证 Session、CSRF、License、项目角色和固定业务输入。Prototype 五类 cursor 使用五个独立的合成测试密钥，不读取或落盘真实 Secret。

`run-edge-browser.mjs` 使用一次性真实 Microsoft Edge profile，执行 Prototype 身份、Package 成员、PROJECT Template、DRAFT Version、服务端校验、正式送审、Link 历史读取及登出后受保护页撤销。送审不是批准，因此本验证不伪造已批准 PrototypeVersion 或 Link 写入；Link 生命周期写入已由 A08/A09 的真实 PostgreSQL/HTTP 验证覆盖。

先构建前端，再运行：

```powershell
pnpm --dir apps/frontend build
python validation/prt-01-a10-a07-windows-browser/verify.py
python validation/prt-01-a10-a07-windows-browser/verify-migration.py
```

仅使用隔离合成数据，不访问外网。退出时清理本轮临时数据库、测试凭据、文件和 Edge profile；截图写入 Git 忽略的 `artifacts/prt-01-a10-a07-windows-browser/`。迁移验证覆盖 0134→0135 有数据升级、旧 NULL 保留、可回滚空新结果，以及新格式结果存在时拒绝降级。登出后直达受保护路由可显示无身份的页面外壳，但不得读取业务数据。
