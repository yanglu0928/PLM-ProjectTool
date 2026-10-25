# P07-A41 Windows工厂前置验收

2026-09-27 Windows11/Python3.13.15/coverage7.13.5，exit0。新增2参数化方法：三公开工厂各3个错误配置，在读取数据库凭据/创建runtime前固定StartupError拒绝；真实Alembic ScriptDirectory在临时空versions目录取得head None，_schema_current返回False且未进入UOW。没有mock成功SQL或伪造head。

完整1553unit/contract失败0、错误0、既有跳过2；原Windows实际登录/发布回归链通过。工厂production_login全文件364/369行98.645%、10/10分支100%，行/分支分母保持。两前置guard已覆盖，五CLI行730/759/779/788/800仍未覆盖，不声称CLI全验。仅临时数据库/合成信任源，不代表正式材料/目标账户/TLS或服务安装验收。

独立runtime auth-security-factory-preconditions JSON SHA256 `a30daa7ecfc73c0848193341fc3a5ca254b2d7daf36f6d4c29f6331356c6a637`；A40原Auth JSON重验`5e9391c09535a78ca715c2625fb2d022905a6fcd6be8e932603a773f2d0bf7bd`未变，旧raw保留，本地产物不上传。完整19链Auth coverage/性能/wheel未重跑，A40完整Auth90%门槛历史通过不改写为本次实跑。

无生产/Migration/API/权限/依赖变，无升级，可撤测试。正式trust/CR008性能FAIL/Gate/可用包未完成。追溯DEC-20260927-389及同名progress/validation，下一P08A01性能约束/现有成本剖析与修复设计，接口/安全调整需独立CR，不降强度或标准。
