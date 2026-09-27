# AUT-04-A08：User创建公开写前置

2026-09-27 / Phase2。读取实际旧User创建/UOW/访问Port、User/Credential ORM/0006不可变历史、冻结API-02 AUTH_USER_CREATE与通用receipt后，结论`HTTP_PRECONDITION_NOT_MET`：无真实Session-CSRF/License Admin生产命令、持久原子幂等和不可变首次UserView，不能直接挂POST。

已先记录CR-AUT-005与DEC293：新Auth owned首次响应/原Credential1密码验证的组合幂等证明，拒绝明文/快速密码摘要与仅username指纹重放；保留原入口/冻结Schema，不把Schema源事实当授权。后续连续0046须完整空/有数据up/down/re-up，已有历史down拒绝丢失。新正常账户仍默认NONE，不顺手实现管理员角色提升。

本项仅源码/冻结事实核查与设计，不新增代码/Migration/API/依赖，不运行新命令/HTTP测试，不标实现PASS。当前已验证A07读取/1277及25回归/wheel保持历史，不作为未来创建证明。Next AUT-04-A09-P01：按CR-AUT-005正式Schema细化/ORM/Migration与source/first-view DTO，前置设计已记录可自主实施；无需普通重复批准，最终包/Gate仍未完成。
