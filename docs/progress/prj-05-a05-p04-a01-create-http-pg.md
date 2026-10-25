# PRJ-05-A05-P04-A01 Windows11 项目创建真实HTTP/PG链

2026-09-28 / 0.1.0.dev0 / `WINDOWS11_SYNTHETIC_PASS`（真实网络和隔离PostgreSQL；真实浏览器待下一任务）。

编码前检查：Phase2/Gate2已批准，输入冻结PROJECT_CREATE及既有Windows显式生产写组合，P03页面合同通过。DEC-411先登记。只扩自有`validation/prj-05-a04-browser-project/serve.py`的独立`--create-api-only`模式，无生产实体/Schema/API/权限/依赖修改或Migration。唯一新临时库/角色/Vault测试源自动清理；合成License Guard不等于正式发行信任。回滚撤验证脚本增量，无数据迁移。

运行：Windows11本机PostgreSQL 18.6/pgvector隔离新库、真实Uvicorn和loopback代理。管理员真实登录→GET管理员用户候选200→带原Cookie/CSRF/Key创建201→同Key同正文重放201同Project ID→同Key异正文409；无Cookie401、普通成员404。终态SQL为3项目（2预置+1新增）、2会话、2有效成员（预置+新负责人）、新项目负责人行1、`PROJECT_CREATED`审计1、COMPLETED幂等收据1。进程exit0后库/角色缺失、Vault CredRead 1168，外部前缀复查库0/角色0。原`--api-only`只读矩阵另轮回归exit0且清理成功。首次调用测试环境缺httpx，按测试依赖安装后重跑；未改变产品依赖。

范围界限：这是后端真实HTTP/SQL与页面所用合同的证据，不是浏览器点击创建、正式HTTPS、正式公钥/可信时间或Server2025/Debian验收；CR-AUT-008性能FAIL、Gate3/完整程序包仍待。下一P04-A02真实Windows11浏览器创建页面与隔离PG终态联调。
