# OUT-01-A01-P16：OutputRequest 取消 Owner 与 opt-in HTTP 结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- 变更：CR-OUT-012
- 代码提交：`f0fefa6434d5362d00ce9c5a26f129bdf954ae6d`
- 验收：GitHub hosted run [41793207115](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41793207115)，13/13 jobs成功
- 执行环境：GitHub托管 Windows/Linux Runner；未在用户本机运行项目程序/测试

## 实施内容

- 新增 OutputRequest cancellation Application Service、锁定读取/状态更新 Repository 和 opt-in `POST /api/v1/projects/{project_id}/output-requests/{output_request_id}:cancel`。
- 新增 Jobs-owned transaction-scoped OutputGenerate cancellation Port/Repository；按OutputRequest → Job → Lease/Attempt顺序重新校验源绑定、Project scope、Job类型/owner/Context ref。待运行Job按既有语义立即取消，运行中只写CANCEL_REQUESTED。
- Owner在同一调用方UOW复验Session/CSRF/License及创建者/ProjectManager授权，使用OutputRequest真实lock_version强If-Match、标准化reason幂等指纹，并同事务同步状态、写Audit与receipt。重放仍复验当前授权并读取同一个OutputRequest；不把运行中的请求取消描述为Worker完成。
- Router保持显式注入，默认/正式组合未挂载；未修改API路径、合同、ORM、Schema或Migration。未加入默认产品组合、未调用AI/插件/客户资料。

## 验证证据

- Hosted backend suite：4,006 tests通过，wheel通过；新增取消Owner 5项单测、HTTP 3项测试包含在全量套件中。
- 同次run前端测试/typecheck/build、PG18/pgvector sidecar重建、同run Python/Backend/Windows父包组装、clean extraction临时PG18/pgvector生命周期、A17 Edge/HTTPS/PostgreSQL和A34离线升级/人工恢复演练、A35/A50均成功。
- Hosted run记录的是父包 PG18 生命周期和既有 A17/A34流程；**没有直接在PG18中执行本取消Repository的新Owner正负行/事务测试**，不能作为此Owner数据库验收。
- 本次没有专用新Owner的运行时父包装配/启用，也没有Output实际生成Worker，因此不能验证真实生成进程结束、RUNNING取消被Worker确认、用户设备可操作性或正式组合加载。

## 已知限制与下一项

1. 真实 PostgreSQL 18 OutputRequest+Job双行/Lease事务、陈旧版本与Audit故障回滚待P17。
2. Output成功/失败Worker Owner当前不存在；运行中取消仅表明请求已登记，未来Worker须遵循CR-OUT-012锁序和fencing。
3. 创建者/ProjectManager Access实现与默认应用组合未接线；opt-in Router不能视作可用产品端点。
4. 正式密钥/License信任、真实用户/Windows 11实机、Pilot/Gate/Release仍未通过。

P16仅按范围限界完成；下一WBS为 `OUT-01-A01-P17`：将取消Owner的正负事务边界接入GitHub hosted PostgreSQL 18验证，并修复验证中发现的问题。
