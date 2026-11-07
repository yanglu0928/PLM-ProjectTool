# OUT-01-A01-P14：OutputRequest 项目列表只读查询结果

- 日期：2026-11-04
- 状态：PASS_SCOPE_LIMITED
- Change Request：CR-OUT-011
- 代码提交：369c8be221be7504e094f1285371155d753f65c0、1446c11bb80e7266a4303963ec227b1e5bd02bec
- 首轮偏差记录：71b2b93f89b106ef609fdfc50ff996fcf807c5f1
- 最终策略测试：b90d65a7eb445adbe01cd955d29fc9cf16e0df67
- Hosted run：[41789030529](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41789030529)

## Changed / Files

- 新增冻结 `GET /api/v1/projects/{project_id}/output-requests` opt-in router。
- 增加 `OUTPUT_REQUEST_LIST` ProjectAuthorization policy：仅 PROJECT_MANAGER、IMPLEMENTATION_MEMBER、CUSTOMER_MANAGER；当前项目成员授权事实按只读锁检查。
- 新增只读 Application Service、精确 ProjectId 过滤的 SQL Repository、稳定 `requested_at DESC, output_request_id DESC` keyset分页与专用 HMAC cursor family。
- Cursor 绑定操作family、Project、Session摘要、page_size、last timestamp/RequestId；校验签名、字段集、规范UUID和canonical时间。
- 只允许 `page_size`、`cursor` query fields，默认50、最大200；项目/权限/许可失败安全投影。
- 响应仅复用固定版本安全 DTO；不取 Context正文、路径、幂等键或Secret。
- 无Migration，未改冻结API Contract，默认Router未挂载。

## Tests / Result

最终Hosted run 41789030529：14/14 jobs成功；后端3,998项测试和wheel、前端测试/typecheck/build、PG18/pgvector、非发行父包、A17 Edge/HTTPS/PostgreSQL、A34替换恢复、A35/A50全通过。

定向用例覆盖role矩阵、授权失败、keyset游标重放/伪造/Scope绑定、分页HTTP、query字段拒绝、只读Project SQL、PostgreSQL dialect编译和敏感列排除。

首轮run 41788380578仅有共享授权矩阵精确计数断言落后：原185项，新policy后186项。已先登记CR-OUT-011，再更新测试预期并断言新操作角色集合与只读属性；最终全量回归通过。产品权限未放宽。

## Known Issues / Limits

- 本次完整父包PG18生命周期 smoke成功，但没有直接使用PG18数据库执行OutputRequest List Repository正/负数据行；SQL由PostgreSQL dialect单测验证。这项PG18行集成仍待关闭。
- API router仍opt-in、未挂默认或正式平台组合；Cursor HMAC key仅有依赖注入接口，没有正式账户Vault/密钥供给。
- 无Windows 11实机、生产信任/服务账户、客户数据、插件/文件执行或发行结论。
- Pilot、Gate 3及正式Release仍NOT_READY。

## Next

OUT-01-A01-P15：对冻结 OUTPUT_REQUEST_CANCEL 进行编码前核查，核对Job cancellation owner registry、OutputRequest状态迁移、幂等/If-Match和Audit同事务边界。
