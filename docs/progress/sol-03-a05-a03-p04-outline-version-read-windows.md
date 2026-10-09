# SOL-03-A05-A03-P04：OutlineVersion 历史读取 Windows 组合与独立密钥恢复

日期：2026-10-09。结果：`SOL_03_A05_A03_P04_OUTLINE_VERSION_READ_WINDOWS_PG_PASS`，限 Windows 11 当前账户与临时 PG18.6；正式服务账户密钥部署和 Server 2025 尚未验。

编码前检查：Phase 2 / 本 WBS；P01 游标、P02 HTTP 合同、P03 双 Scope 真实 ASGI/PG 均通过。仅修改 Solution Windows 组装及生产入口、增加独立游标密钥适配器/测试/验证脚本；不改 Schema/Migration、冻结 API/角色、其他业务模块。沿用现有 Windows 当前账户 Credential Manager 只读密钥和加密备份恢复机制。P04 组装中识别旧部署新增密钥前置，已补记 `CR-SOL-019`，不冒充事前记录。

新增 `project-outline-version-list-cursor-v1` 专用 32 字节 key 引用，与 Outline、Section、Reference 等游标引用隔离；当前账户凭据缺失/长度错误统一拒启动，不自动生成/覆盖正式 key，也不将 key 写入仓库或日志。生产只读与读写模式组装真实受权 Owner/路由，登录专用模式不注入。单元测试使用随机临时引用验证失密、加密备份恢复后旧游标可解，最终清理临时凭据；未触碰正式目标。缺 key 时生产两模式拒启动并释放数据库资源，隐藏具体敏感异常。

验证：定向 41 通过/17 子例；Windows 11 隔离 PG18.6 上 Windows 工厂真实双 Scope ASGI/PG 历史、分页、拒绝链退出 0；后端全量 3469 通过/3 跳过/5333 子例。未验证实际目标服务账户的 Vault/ACL/恢复、Windows Server 2025、本项前端/浏览器、20 并发或正式发行。下一项历史列表/详情页面与浏览器；Gate3/发行仍 BLOCKED。

TraceLink：Gate2 API-04 → A05-A02 Owner → A05-A03-P01/P02/P03 → CR-SOL-019 → 本 Windows 组合 → UI/浏览器。
