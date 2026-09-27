# AUT-04-A02：User详情HTTP

2026-09-27 Phase2编码前PASS；冻结API-02 AUTH_USER_GET、当前0045/A01真实User安全Reader已验。仅可选GET `/api/v1/admin/users/{user_id}`，无写、列表或Windows自动装配。

DEC287：沿原Session.validate→同UOW当前Admin/License Reader顺序，未知/无管理权限统一404，过期Session401、Host403、License403；严格public View/目标绑定，强vN ETag/no-store/nosniff。GET不要求CSRF/不更新Session。If-None-Match不绕授权，仍真实200；未知query400、零UUID404、畸形UUID通用422。无Migration/新权限/依赖/Breaking，默认404，回滚撤router保历史。

验收：单位API安全字段/错误/畸形源/默认404；真实PG Session/Admin/撤权停用/目标DISABLED/ETag与Credential版本分离/五表无写/现有回归。风险：正式信任与部署/列表/用户写生命周期未完，不宣称完整管理面/包/Gate。

执行结果：WINDOWS_HTTP_INTERNAL_PASS。5新Contract/1258后端无失败（2既有权限跳过）；真实PG当前Session/Admin/合成License、普通404/未知与实际撤销Session401/未知目标404/Host403/query400、目标DISABLED可读、rename技术fixture使ETag增长而Credential版本不变、If-None-Match撤角色仍404，五表全行无写。A01内部读与原双Scope文件发布/失败回滚回归通过。

开发wheel686062字节，SHA256 4e3473540cb423a6f17244657b37762d2fafca4b2d71c3330f6a070049c04526，非可用安装包。无Migration/依赖/角色/Breaking，原冻结保留；默认404，Windows尚未挂。回滚撤可选router保历史，升级无新动作；正式信任/列表/管理写/锁竞争/性能/三平台/完整包/Gate待。Next AUT-04-A03 Windows两显式platform装配与缺依赖失败关闭。
