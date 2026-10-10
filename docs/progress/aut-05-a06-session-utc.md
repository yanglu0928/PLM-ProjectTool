# AUT05A06 Session UTC 响应一致性

2026-09-28 / 0.1.0.dev0 / PASS（冻结UTC wire format 的Auth三响应，Windows11合成范围）。

编码前检查：Phase2/AUT05A06；输入Gate2 API合同 `64cdf09`、CR-AUT-009、A05浏览器PG偏移实证；前置Gate2/A05已满足。模块Auth HTTP；实体仅Session过期时间投影，不改存储；API为原登录、当前会话、续期三个成功响应；权限、Cookie、CSRF、审计不变。验收三响应对偏移源输出UTC-Z且保持原时刻，原真实网络链完整通过，naive/错类型拒绝。风险、兼容、迁移/回滚详见CR-AUT-009。

Changed：共享Auth时间wire formatter，登录/GET/续期使用它；原A04实际网络验收新增三个成功响应UTC格式断言，不变更原请求及审计计数。新增正负时区与UTC单元测试，三个合同测试覆盖各响应。无ORM/Migration、公开字段、权限或依赖变化；现有数据库0049无需升级。前端A05严格offset兼容保留，服务端如今满足冻结合同。

Tests：关联15项PASS；后端全量1558项无失败（2项既有符号链接账户权限跳过）；原真实PG18.6/Windows工厂经Uvicorn/Vite 9GET/12POST原链PASS，三个Auth成功响应均UTC-Z，原Cookie/CSRF/replay/并发/Audit及自有临时源清理断言未放宽；开发wheel构建PASS。此前首次误用pytest运行器缺依赖，切回项目既有unittest且未增依赖。Frontend本项未改，本项不重复浏览器交互；A05真实浏览器PASS不冒充本项端到端复测。

Known issues：CR-AUT-008 20并发密码写P95仍FAIL；正式信任锚/目标账户、HTTPS、Server2025/Debian、全范围UAT/可使用包与Gate3仍待。导航间距为独立UI排版任务；不会将合同格式修复当作完整发行证明。
