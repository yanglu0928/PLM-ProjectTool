# PLT-PKG-01-A09-P51-A19：父包清洁落地及 PostgreSQL 生命周期前置检查

- 日期：2026-10-27
- 状态：编码前检查通过，限于 GitHub hosted Windows runner 上的非发行父包与内置PG组件。
- 前置：A18父包候选 run 40457725517/artifact 12712678647，完整ZIP摘要 `089daa5375a64b3a2c4533b85efcc0237c534dd232f66013ddbb3d8fe13b89b8`；PR #55。Rules V1.1及PLM项目Skill已恢复。
- 用户硬约束：不在用户本机执行；runner临时根必须位于非C盘，所有测试为合成空数据库且在作业结束回收。

## 问题和边界

A18证明了三组件父包内容/摘要完整，但未安装或启动。当前只验完整父包可安全清洁解包以及包内PG18/pgvector能在runner-owned临时目录初始化、启动、查询vector扩展并关闭。此项不做SCM安装、服务账户ACL、产品License信任注入、API/Edge/HTTPS启动、OCR模型推理或用户数据迁移；数据库启动结果不能视为产品启动或Pilot。

## 检查

- 读取父包artifact的verification summary，要求same workflow run、source commit、release/legal false与精确archive SHA。
- 解包前检查每个ZIP路径、重复/大小写冲突、符号链接、元数据及总payload摘要；只写入runner temp的非C盘独立根。
- 从payload/pgsql运行包内initdb/pg_ctl/psql，数据库监听仅127.0.0.1，随机临时端口，trust仅本地一次性空库；建库并查询PostgreSQL版本、安装vector extension并查询扩展版本。
- finally停止本轮创建的PG进程并清除其独立临时目录；确认端口连接关闭，输出无密码/数据库日志，只上传机器可读验收摘要。
- 任一步失败均阻断验收artifact，不删除runner外路径。

## 预期结果与回滚

期望 `PARENT_PG18_TEMP_LIFECYCLE_PASS_LIMITED`。失败时记录失败步骤与清理结果，作业runner资源随后回收；不改旧artifact或正式数据。成功也仅证明PG组件包内二进制运行/pgvector注册，不证明应用安装、正式权限/License、OCR、HTTPS、Gate或Release。

## 下一步

如该切片通过，先以同样隔离原则检查应用启动前置及缺失正式信任条件；若正式信任材料缺失，则显式记录 fail-closed 并继续完成可独立开发的安装/配置/版本说明任务。禁止用临时测试公钥冒充正式公钥。
