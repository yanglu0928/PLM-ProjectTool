# AUT-04-A12-P06-A01 密码管理20并发基线

编码前检查：Phase2；WBS P06A01；输入冻结64cdf09/API02、CR-AUT007及0049，前置f8d9432内部Windows完整reset/change通过。涉及Auth Session GET/reset/change及不可变first/receipt/Audit；只增加隔离验证，不改生产模块/Schema/权限/依赖/API。使用Windows实际write Factory，真实PG18/Scrypt与当前Session/CSRF；正向License/密钥明确合成。

DEC-20260927-324：20个独立异步客户端通过同一ASGI应用同步放行，测完整HTTP处理时间（非网络/浏览器/正式服务）。测Session GET、20独立目标reset及20本人change，真实结果/凭据版本/全Session撤销核对；P95最近秩ceil(.95*n)，GET<=500ms、普通写<=1000ms。安全与性能分开判定；失败不降标准。当前global advisory lock内Scrypt存在排队风险，先测真实基线再记录偏差/最小修复设计。仅合成用户/拥有的临时DB/文件，不访问客户资料或外发数据。

回滚：本轮仅验证/文档，撤脚本不改变生产行为，既有历史不删。未验TCP/TLS/浏览器、正式供给/服务账户、20并发持续负载、跨平台及完整包；Gate3/CR不提前关闭。

## 实际结果：密码并发FAIL，诊断完成

三轮真实运行均reset20成功但P95约5.60～5.69秒、change14成功/6失败503且P95约7.30～7.36秒；GET20成功且P95约108～120ms。第三轮实际SQLAlchemy handle_error诊断六个`55P03`全部来自deployment advisory lock。固定Scrypt在全局锁内导致排队/5秒锁超时，不用猜测错误类别。

第二/第三轮补核失败事务：六用户仍凭据/User版本2、两条历史Credential、原受限Session仍有效，没有change first/PASSWORD_CHANGED审计；成功用户版本3/唯一first且旧Session失效/真实新密码签发验证。20reset first/14change first数一致。原Windows状态及双Scope发布回归通过，不抵消本次功能/性能FAIL。

首次脚本在并发非全200后立即断言，故未执行后续完整性及原发布；随后改为先收集安全错误与真实rollback证据并跑完回归，最终以非零退出明确FAIL，不把脚本退出正常冒充达标。数据均临时隔离fixture清理，无生产操作/客户正文。1388 unit为上一轮结果，本轮未重跑/未重建wheel，因为无生产代码变化。

新增CR-AUT008比较并记录预认证/释放事务/KDF预计算/原全局事务完整重验方向，尚未实施；保留强度/锁/权限/历史恢复标准。完整验收缺项矩阵另文件记录，当前CR/Gate/安装包未通过。下一P06A02先精化reset预计算proof/事务边界及真实撤权竞争验证，再处理change/replay，不能提前宣称性能已修复。

最终退出语义复验（第四轮）：GET P95 113.978ms；reset20成功/P95 5653.504ms；change14成功/6个503/P95 7301.987ms；六SQL仍均55P03/deployment advisory lock，完整性计数20/14/6正确，原Windows状态及发布回归通过后脚本实际exit1并明确PASSWORD_CONCURRENCY FAIL。该非零是验收失败，不是观测超时或进程仍运行；未重新启动任何活句柄。
