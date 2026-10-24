# PRT-01-A11-A05-P01 隔离物理文件/PostgreSQL 验证

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p01-physical-pg/verify.py'
```

脚本只在本轮新建的 ASCII Temp 子目录复制已验证 PG18.6/pgvector 运行件，随机 loopback 端口与临时 `trust` 认证仅供合成验收；迁移当前 Schema，创建合成 Document 与真实磁盘文件，检验当前内容通过、跨项目/篡改/文件缺失拒绝。停机确认后仅删除本轮目录，不访问旧集群或客户资料。该验证不能代替完整 Prototype Owner/HTTP/并发性能验收。
