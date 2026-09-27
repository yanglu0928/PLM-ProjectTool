# AUT-04-A09-P05：Windows显式写User创建

2026-09-27 / WINDOWS_WRITE_INTERNAL_PASS，非正式账户/完整发行验收。

编码前检查：Phase2 / AUT-04-A09-P05；输入冻结API02/CR-AUT-005/0046/P04可选HTTP，前置dc4da7a已同步。仅Windows composition接线/Auth相关验证与版本记录，无Schema/依赖/角色/新KeyRef。沿原强制信任/Session/真实Scrypt/User Repository/currentAdmin/License/Audit/receipt；禁止生产合成fallback。

目标：仅显式platform-write挂User创建POST；platform只读GET-only405、default/login404。构造Service/results/replay/router故障拒绝半启动并dispose；真实当前Admin HTTP首次/原Key重放与禁用历史/安全错误、创建后真实登录HTTP可用、原读取/写回归。实际缺正式信任仍拒绝，正向测试供给明确Synthetic，不外推正式账户/三平台/性能/完整包。

升级兼容：head0046沿P01维护备份/迁移要求；本项无额外密钥供给，仍依赖原正式公钥/可信时间/Secret/cursors/Upload等。回滚撤User create wiring保全部历史/旧GET入口；不改变readonly范围，不提升新User部署管理员。

## 执行证据

- 仅`include_secret_write`接实际Scrypt/原Auth Repository/当前Admin Adapter/first/result ReplayVerifier/receipt/Audit/License；readonly不构造新依赖。新Contract test四dependency fault实际调用且dispose；全后端1305无失败（2既有Windows符号链接权限场景跳过）。
- `validation/aut-04-a09-p05-windows-user-create/verify.py`实际Windows write Factory/PG18-ASGI：复用P04完整当前Session-CSRF/201/冲突/历史停用重放及原P03并发/rollback/确认丢失；新账户真实登录HTTP→HttpOnly Cookie→当前Session，deployment_role NONE不能创建用户，原Admin重放不额外写。七表完整snapshot含rate buckets对重放/拒绝无写。
- readonly GET-only POST405、新四构造器不调用；write四依赖故障到达拒绝，default/login404；退出所有positive trust注入后实际Factory缺正式材料仍拒绝。正式key/License未供给，本正向显式Synthetic信任不作为生产来源。
- 首轮登录断言把冻结SessionView的嵌套`data.user.user_id`误当顶层，修正validator后整体重跑通过；不改原合同。没有真实TLS监听服务/浏览器或正式账户证明。
- A07实际两Windows User列表与发布、`job-03-a02-p05-windows-retry`实际当前用户新代重试/Worker文件成功、`job-01-a05-p05-windows`实际混合Audit/Document任务列表及各自原发布回归exit0。未本轮重跑所有25旧脚本，不外推其他未验Owner。
- 开发wheel702222 bytes、SHA256 `84637e448af479e12d8eea6050eec14434a44d805df41e5434a8fe4d583582fd`，本地忽略开发产物，不是用户可安装交付包。

Changed/Files：production Windows wiring、constructor Contract、实际Windows validator、本文/DEC298/API增量/CR/STATUS/CHANGELOG。Migration/API：无新Migration/依赖/Key/权限，head0046；冻结POST仅显式写模式开。Result：P01～P05创建链内部验收完成。Known Issues：正式信任/目标账户、三平台/20并发/吞吐与完整管理/UI/安装升级/质量/Gate/最终包仍待，CR完整发行不关闭。Next：AUT-04-A10-P01 User显示名称PATCH/强版本/唯一性/当前权限前置核查与内部实现。
