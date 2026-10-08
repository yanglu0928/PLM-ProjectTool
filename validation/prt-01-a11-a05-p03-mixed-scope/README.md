# PRT-01-A11-A05-P03-A02：混合范围真实验收

在仓库根目录运行：

```powershell
$env:PYTHONPATH=(Resolve-Path 'apps/backend/src').Path
& '.poc-runtime/prj05a05-p04-venv/Scripts/python.exe' 'validation/prt-01-a11-a05-p03-mixed-scope/verify.py'
```

两条合成Requirement均在REQUIREMENT阶段经正式服务创建、送审和客户角色审批，Checklist保留两个Review轮次，然后才推进PROTOTYPE。隔离PostgreSQL18.6/pgvector中，第一条由正式Approved PrototypeVersion、真实Document文件和完整ACTIVE Link覆盖；第二条由项目经理作NOT_REQUIRED决定，Audit必须可证明。缺少第二决定时拒绝两项资格；预览后篡改原型文件，Checklist写时仍拒绝。恢复后按当前Scope登记PASS并推进SOLUTION。另一次独立隔离库将第一条同时放入NOT_REQUIRED和Approved Prototype，验证资格409且不形成Prototype Checklist历史。客户角色和PM均为合成测试主体，不表示客户真实确认。

与A01共用验证逻辑，但两种场景各用独立随机库和受控临时实例，退出时停机清理。此项尚不证明更复杂的多原型重叠/部分覆盖、20并发、生产信任源或其他目标平台。
