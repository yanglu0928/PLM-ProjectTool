# AUT-04-A12-P05-A06 可选reset HTTP

编码前检查：Phase2/Gate3未通过；基线64cdf09/API02 AUTH_USER_RESET_PASSWORD S,L,C,I,M,A、CR-AUT007/0049，前置fee5973原子reset已实际验。Auth可选POST，无新Schema/依赖/权限；现有强If-Match解析、来源/Session-CSRF-Key及有界strict JSON。

DEC-20260927-322：body仅temporary_password字符串与严格true must_change_password，path目标/expected绑定Service；normal Admin/License由真实Service前后检查，失败权限隐匿404，版本/同Key差异409。data仅credential_version，可从first.user_version返回目标强ETag（并非credential_version）；历史重放保first ETag，当前请求trace。self成功明确旧Session失效才清安全Cookie，normalAdmin新认证重放保新Cookie，unknown末读503不猜回滚。default404/Windows另项。

验收：实际PG-Scrypt-ASGI拒绝矩阵九表不变、正常/disabled/self、强If-Match缺失428/坏格式400/旧409与重放原版本、write-only密码、安全响应/ETag/Cookie，实际Audit后故障回滚与提交后末读503改密新登录原Key恢复。旧与受限Admin均不授新管理写。回滚撤可选router保历史不复活Session。完整浏览器/Windows/性能/三平台/正式trust/包/Gate未验。

## 执行结果（2026-09-27）

可选router与四项HTTP unit完成。真实隔离PG18/Scrypt-ASGI验证通过：浏览器来源、Session/CSRF/Key、If-Match及严格有界JSON拒绝九表不变；正常目标、停用目标保DISABLED、self首次Cookie清除及受限身份拒绝；真正change后的新Admin登录历史重放保原结果/ETag及新Cookie。disabled/self的凭据版本2与User ETag v3分别验证，未混用。

实际Audit写后故障503整体回滚；实际self提交后末读故障503不清Cookie、不猜回滚，真实临时登录→改密→正常Admin新登录后原Key恢复首次结果且九表不再写。原双Scope发布回归通过。License及角色初始来源明确为合成/TEST_ONLY，不是正式信任证明。

后端1388 tests无失败（2既有跳过）；开发wheel 749262 bytes，SHA256 `082a30057055c7fcce8b47d514dd5cedb48ceb15c9b8d4c48dc7a61be483c14b`。无新Migration/依赖/生产升级，Schema仍0049，默认404；Windows实际工厂装配下一项A07。此为内部HTTP PASS，不关闭CR/Gate、不作为可用安装包交付。
