# CR-AUT-007 受限Session投影增量

2026-09-27 / 0.1.0.dev0 / WINDOWS_RESTRICTED_SESSION_PROJECTION_VERIFIED。
原冻结64cdf09保留；AUTH_LOGIN、AUTH_SESSION_GET、AUTH_SESSION_RENEW路径和现有字段不变，增加data.password_change_required（严格boolean）。

- false：普通身份、原deployment_role及authorized_projects继续返回；不改变既有角色含义。
- true：仅身份、现有到期信息及适用的CSRF材料；deployment_role固定NONE、authorized_projects空列表，服务端不读取项目清单。NONE表示此会话不展示管理权利，不改写User真实角色。
- Windows按真实Token/User/当前Credential精确绑定，旧/未知会话不能通过只给UserID取得新投影；缺源/绑定错误503且不回退。实际业务权利仍由Auth Ports实时核查，响应不是授权凭证。
- 受限Session可以读取最小当前身份、续期受限身份和退出，不能通过续期解除must_change标志。改密HTTP尚未实现，不能凭此状态宣称完整可用的首次改密流程；reset接口仍关闭。

测试证据见A12P01/P02 progress；合成License/显式TEST_ONLY凭据和角色仅验证内部行为。无本轮Migration/依赖，兼容0047；正式信任/性能/三平台/浏览器UI/安装包/Gate3未验收。
