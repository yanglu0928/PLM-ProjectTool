# P07-A40 完整Auth覆盖门槛结果

2026-09-27 Windows11/Python3.13.15/coverage7.13.5（仅测试依赖），exit0。1551unit/contract失败0/错误0/既有跳过2，原17链+成员名称实际来源+初始管理员临时PG初始化，共19实际链全部通过。

完整Auth全部文件3300/3382行97.575%、890/988分支90.081%，综合95.881%，行/分支各90%门槛均通过。范围未删、无排除/pragma或门槛变更；相对A32行分母+3为已记录UserList等价布局、分支988保持。改善含新增真实用例/实际链及布局映射，不全称新增行为覆盖。仍有98缺失分支，门槛达到并不证明所有安全行为已验证。

原密码21文件1031/1047行98.472%、350/384分支91.146%保持。Windows完整factory362/369行、8/10分支单列（80%），不能借Auth门槛通过豁免工厂缺口。两缺失guard223→224（Migration head None）、261→262（settings类型错误）下一独立验证，其他未覆盖CLI行继续按实际范围记录。

独立runtime auth-security-bootstrap-coverage JSON SHA256 `5e9391c09535a78ca715c2625fb2d022905a6fcd6be8e932603a773f2d0bf7bd`；旧A32重验`c5cc762578c3cffb1abcdd3f27e244bd5c6a6a832fc1c313a2c0e5db7fd798bf`未变，全部历史raw保留，原始产物/诊断/密码/客户数据不上传。

仅完整Auth覆盖验收项通过，不是性能/生产trust/真实服务与TLS/全部异常/三平台/UAT/Gate 3/可用程序包完成。性能及wheel未跑，无生产/Migration/API/依赖变化，无升级。CR008性能FAIL/正式材料等缺项保持。追溯DEC-20260927-388及同名progress/validation，下一Windows工厂两个前置失败关闭合同，再继续正式运行与性能验收。
