# AUT-04-A10-P03 Windows写模式User名称PATCH

## 编码前检查

- 当前Phase/WBS：Phase2 / AUT-04-A10-P03，Gate3未关闭。
- 输入/前置：冻结API02与0046；P01内部和P02可选HTTP fff5e83真实PG/1319测试通过。
- 模块/实体/API：Auth/User；Windows组合根，只接冻结PATCH。
- 权限：原当前Admin-CSRF/License/Audit/UOW；不新增权限/信任回退。
- 验收：actualFactory执行P02真实HTTP矩阵、改名后真实登录新名与旧名拒绝，原Session仍有效；readonly405/default-login404；新依赖故障真实到达/安全启动失败/dispose；退出合成信任后实际缺正式材料继续拒绝。
- 风险：正向信任显式合成，非正式账户/监听代理/三平台证明；名称改变影响登录，原创建重放仍历史。

DEC-20260927-301：只include_secret_write挂名称PATCH，复用原UOW/currentAdmin/License/Audit，无新Key/Schema/依赖。撤wiring保历史。

## 执行结果

- Result：WINDOWS_COMPOSITION_INTERNAL_PASS；非正式发行验收。
- Changed/Files：production_login只write构造原P01 Service/Repo/P02router，传create_app显式参数；扩展原生产构造异常unit至三个新依赖，实际Windows隔离PG脚本。
- Tests：1319无失败（2既有符号链接权限跳过）。actualFactory执行P02全部真实Session-CSRF/版本/输入/权限/唯一/历史矩阵；新建真实Scrypt用户→登录→改名后旧名401/新名200同UUID，旧Session仍有效、NONE不可改名，原首创建201v1重放七表不变。readonly405且三个新构造不调用；write三故障确实到达并失败关闭，unit runtime.dispose一次；login/default404。退出合成信任后实际缺正式材料拒绝且七表不写。
- Regression：旧Windows创建P05完整原密码/重放/HTTP登录/权限/四构造故障与缺信任拒绝回归通过；原双Scope空/260行实际文件发布及权限/取消/许可/故障/锁竞争回归通过；未重跑全部历史脚本。
- Build：开发wheel706776字节，SHA256 `1f4e7d6befb639d202f107742c6f234eb4cdfb2bf47f928448e92ffeb314a88f`；非安装包，不提交wheel。
- Migration/API：无新Schema/migration/依赖/权限/Key，沿0046；冻结PATCH仅显式Windowswrite挂载；原冻结版本保留。
- Known Issues：正向信任显式合成；正式目标账户/服务监听/HTTPS代理/真实浏览器/20并发性能/提交确认故障HTTP/三平台/UI/完整包与Gate3未完成。
- Next：AUT-04-A11-P01 User enable/disable前置核查，重点锁版本/同事务全Session撤销/持久幂等首次响应/审计与自停用、最后Admin策略；冻结冲突先记录CR，不直接公开入口。
