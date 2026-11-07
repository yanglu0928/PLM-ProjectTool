# OUT-01-A01-P25：真实 HTTP 与 Edge 失败关闭验收结果

- 日期：2026-11-06
- 结论：`PASS_SCOPE_LIMITED`
- 证据运行：[GitHub Actions run 42217889515](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42217889515)
- 验证提交：`06f75f1bda0cef39a97de6b890e15c81d5777b2c`
- 环境：GitHub hosted Windows Server 2025，D盘 Runner Temp；隔离 PostgreSQL 18.6、pgvector 0.8.6；Edge headless。

## 结果

- 全链16/16 jobs成功：后端全量测试和wheel、前端全量测试/类型检查/构建、PostgreSQL sidecar和父包构建、A17/A34/A35/A50/P24/P39及P25均完成。
- `GET /health/live` 返回200、JSON MIME及固定UP。此前尝试的`/openapi.json`返回404是因FastAPI显式关闭OpenAPI/docs；已改成正确健康探针。
- Edge通过真实loopback HTTP桥接到显式Windows Output Create组合。用户动作触发且仅触发1次Output Create POST，FastAPI返回422/ `VALIDATION_FAILED`，页面显示预期固定版本校验提示。
- 无成功受理或状态回执、无自动重试。目标Output/Job/Audit/Idempotency表计数前后相同；父包提取、PostgreSQL和浏览器临时资源清理成功。
- 根因：Harness代理分支误引用`api(req,url)`函数内声明的局部`entry`，而代理代码位于外层HTTP callback，造成fetch前ReferenceError。按CR-OUT-021将请求记录绑定到`req.__p24Entry`后复验成功。
- 过程偏差均保留：OpenAPI探针路径错误、Git tree基准落后造成代码树暂时回退、代理entry作用域错误；使用普通前向提交恢复/修复，未force push，详细记录见CR-OUT-021。

## 限制

本结果只证明指定Hosted合成环境下真实API拒绝路径、UI提示和数据库无写入。它不证明Windows 11本轮实机、真实客户数据、正式License/Publisher trust、服务身份ACL、TLS、产品启动、DOCX生成、插件执行、Pilot、Gate 3或正式Release。默认Create路由仍未挂载。

没有客户正文、Secret、外部AI/API或插件；没有在用户本机/C盘运行项目代码。所有程序代码和数据库均在GitHub Hosted Windows Server 2025 D盘临时环境。
