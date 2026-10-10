# P06-P12-B02：真实 PostgreSQL Windows 子进程

2026-09-27/Phase2，CR-AUD-004，前置P11固定Windows装配和P12-B01停止边界内部通过。编码前：只新增验证脚本，Audit/Jobs/Document真实既有实现，无API/权限/实体/Schema/依赖变化。目标：独立隐藏进程经实际CLI和YAML装载、真实临时Windows DB Credential与Vault SystemActor完成PROJECT/DEPLOYMENT发布；缺正式包内公钥关闭且六表不写；外部CTRL_BREAK idle与active停止/第二任务未领取。测试License Guard显式替身，不声称正式License通过。

计划：父进程隔离PG库/临时文件/凭据；仅非秘密引用和路径传子进程，URL和主密钥不入argv/env/文件。复用P12-A发送器严格Console清单控制。实际文件摘要、结果、Job/Lease/Attempt/Audit交叉核验；活动存储I/O测试门只用于确定性停止时间点，释放后原真实发布执行。超时观察同一进程，不重启；失败先私有STOP/RELEASE正常收口，不强杀。所有子进程退出后才删本轮凭据/库。风险仍有无限阻塞/SCM/正式来源/其他平台/完整包/Gate。回滚撤验证脚本，无升级/Migration。

实际结果 INTERNAL PASS：六个独立隐藏Windows Python3.13子进程（缺源1、双Scope once2、idle1、active1、第二任务once1）使用真实CLI/YAML/有界PG18当前Schema/临时Credential/Vault identity。双Scope与活动排空后任务真实SUCCEEDED，实际文件AVAILABLE/长度/SHA256匹配不可变结果，单次Attempt完成无错误/Lease RELEASED，发布SYSTEM actor与父进程真实Vault identity一致。缺真实包内公钥退出1且六表不写；idle外部CTRL_BREAK STOPPED/0执行且六表不写；active外部CTRL_BREAK原任务成功/第二任务PENDING且无Attempt，再次独立once完成第二任务。所有子进程退出、临时DB Credential删除后原fixture清理Vault/数据库/文件；没有正式秘密外发。原发布空/260及并发/失败回滚测试同次通过。

License明确为TestOnlyGuard；正式默认Credential、真实发行公钥/可信时间/选定MAC没有供给验证；活动门是测试同步点，不证明所有阻塞I/O及时停止。无生产代码/API/Migration/依赖/升级变化，不重构建未变wheel。下一P06-P13检查公平性/坏来源隔离；SCM/硬终止/未知跨进程恢复/HTTP/完整产品/Gate仍待。
