# PLG-02-A07：PluginInstallation只读详情 API 结果

- 日期：2026-11-04
- 状态：`PASS_SCOPE_LIMITED`
- 变更记录：`docs/changes/CR-PLG-012-plugin-installation-read-api.md`
- 编码前核查：`docs/progress/plg-02-a07-installation-read-precheck.md`
- 验收运行：[GitHub hosted run 41759878694](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41759878694)
- 源分支：`feature/p51-a33-launcher-checksum-recovery`

## 已交付

冻结接口 `PLUGIN_INSTALLATION_GET` 已形成读取服务、SQLAlchemy Repository 和HTTP Router，路径为 `GET /api/v1/admin/plugins/installations/{installation_id}`。

- 读取前后均核验Session与DeploymentAdmin；License检查在数据读取前执行。
- 响应由固定字段白名单构成，不返回原始签名、安装路径、环境、ORM对象或错误堆栈。
- 返回当前`lock_version`和强ETag `"v<lock_version>"`；响应设置`Cache-Control: no-store`。
- GET不要求CSRF，无query参数，不改变安装事实；不存在和未授权对象不可区分。
- 只在显式Production Platform Read/Write装配；默认应用仍不挂载该路由。
- Manifest中文名称按合同允许显示，验证器只排除空名、超长名与控制字符。

## 验收证据

run 41759878694全13/13 jobs成功：

- 后端全量测试3967项、wheel成功；前端测试及构建成功。
- hosted PostgreSQL 18.6真实SQL路径用合成ENABLED安装读取详情，断言状态、`lock_version=1`、ETag `"v1"`、操作集合、包SHA一致及签名未进入RuntimeSnapshot；中文显示名由同一签名合成Manifest覆盖。
- 新增TestClient HTTP测试覆盖白名单响应、ETag、no-store、query拒绝；应用工厂测试验证显式挂载成功、默认工厂为404。
- 父包20,176项在hosted Windows Server 2025的D盘Runner临时区完成构建、清洁解包与PG18/pgvector smoke；父包SHA-256：`cd54f676a659a1e993136b6ac90127c062034008f91483dd4c21ae2b65d9a6a7`。
- 同一run的A17输出为`PASS_LIMITED`，状态IN_REVIEW、决策数0，且明确为hosted Windows Server 2025合成流程；A34手动恢复演练、A35候选分片交接、A50源导航成功。
- 修正前首次run [41759144508](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41759144508) 因FastAPI内部路由包装对象没有公开`.path`失败。偏差已先写入CR-PLG-012，测试改成HTTP行为断言后，全量run通过。

## 范围限制与未通过事项

该结果仅证明合成数据下的只读链路及托管SQL/HTTP自动化验收。没有在用户本机、C盘或Win11设备执行代码。产品API未启动；真实正式License/公钥、服务账户数据库凭据、ACL、TLS尚缺。真实宿主安装、物理卸载、插件执行仍未实现。本结果不表示Gate、Pilot、正式Release或正式信任通过。

回滚不需要Schema迁移；移除本项Read Service/Repository/Router和显式组合即可，不更改既有Installation事实。
