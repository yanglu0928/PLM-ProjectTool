# AUT-04-A01：User管理安全详情内部读取

2026-09-27 / Phase2编码前PASS。输入冻结64cdf09 DM-02/API-02 AUTH_USER_GET、当前0045、AUT-01/AUT-03与真实Admin read access。核查User/Credential已有表、生产Hash/Session/License Port；当前无User管理GET，原内部创建缺持久幂等，不能直接公开写。

本项仅Auth内部详情读取：当前Session/ENABLED DeploymentAdmin和License，显式最小User投影user_id/username_display/account_state/deployment_role/credential_version/created_at/updated_at/lock_version。禁用目标可被Admin读取；用户名canonical、credential ID/hash/parameters、token、CSRF、保留策略不返回。读取锁定当前授权与目标，无commit/Audit写；强版本沿现User lock_version，不把CredentialVersion冒充ETag。无API路由/Migration/新角色/依赖。

验收：真实Admin/普通用户/撤Session/过期License/未知目标/禁用目标、元数据零秘密、异常静态错误、读取无写及既有回归。风险：目标User共享锁与管理写交错，后续HTTP/并发/列表/游标/用户启停重置幂等另项验证；不能据内部GET标完整管理面。回滚不调用新服务，保历史。

## 执行结果：WINDOWS_INTERNAL_READ_PASS

- 新`auth/application/user_read.py`严格Query/View/current授权Service，token不进入repr，UUID/真实aware时间/状态/版本严格验证，两次License Guard、实际当前Admin、同UOW目标锁、无commit；未知目标固定RESOURCE_NOT_FOUND、故障静态AUTH_READ_UNAVAILABLE。
- 新`auth/infrastructure/user_read_repository.py`只select八项public metadata列，目标共享锁；不查询密码凭据、canonical用户名、retention或整行序列化。Admin权限与Session行锁由原Auth owned Access保证；不新增角色/权限。
- 六项新unit（包含多场景子矩阵）覆盖无权不读目标/字段白名单/禁用目标/非法输入与源/错误绑定/最后Guard故障/no commit；后端1253无失败，2既有符号链接权限跳过。
- 实际PG18/Python3.13/Win11：当前Admin可读取普通ENABLED目标；目标DISABLED仍可读；普通/未知/实际revoked Session、未知目标、管理员角色降权与DISABLED、合成License拒绝，五表完整snapshot无写。原实际Audit双Scope文件发布/错误回滚回归通过。
- 初次撤Session夹具漏revoke_reason与lock_version递增，被冻结触发器拒绝；补齐既有合法撤销shape后完整隔离链通过，不更改Session保护。夹具撤销不是本轮实现的公开管理命令。
- 开发wheel684687字节，SHA256 df383d752204abd39fd05c602c0247fe73402aad21a6cd9372ddf09da8905b04，非可用安装包。

Migration/API生产路由/依赖/架构：无，兼容现0045，升级无新步骤；回滚不调用新Reader保历史。正向License合成；HTTP、Windows挂载、列表/游标、管理写幂等/账户生命周期、交叉锁竞争/覆盖率/性能/正式供给/三平台/完整包/Gate未验证。Next：AUT-04-A02可选冻结`GET /api/v1/admin/users/{user_id}`安全HTTP、真实Session及强ETag，仍不顺手开放写API。
