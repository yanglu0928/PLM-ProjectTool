# AUT-04-A11-P01 状态命令前置与Domain合同

## 编码前检查

- 当前Phase/WBS：Phase2 Platform Core / AUT-04-A11-P01；Gate2原64cdf09保留，Gate3未通过。
- 输入基线：V2.1、总控V1.1、License CR-LIC001、DM02/SC02/API02、当前0046及AUT04A09/A10。
- 前置：读取现有User/Session/通用receipt/0046first，已确认缺状态首次结果；先CR-AUT006记录增量再纯Domain/DTO。
- 模块/实体：Auth User状态与首次结果，其他模块不修改。
- API：冻结enable/disable内部合同；本轮不挂HTTP。
- 权限：Domain不是授权；未来真实Session-CSRF/Admin/License及锁定计数由Application/Repository证明。
- 验收：转换/版本/凭据/最后Admin保护严格类型/异常；自停用在存在其他Admin时不被全面禁止；firstDTO版本+1/状态/来源/时间/计数及不可变。
- 风险：DB状态原子性/所有Session撤销/自停用特殊末核/真实竞争尚未实现，纯规则不证明真实安全。

DEC-20260927-302：按CR-AUT006选择独立状态first与原receipt原子组合；P01只前置与纯Domain/DTO，P02 Schema、P03内部同事务、P04 HTTP、P05 Windows逐证据推进。无本轮Schema/API/依赖/生产操作，撤纯未接线文件保旧路径。

## 验证结果

- Result：PRECHECK_AND_DOMAIN_PASS；状态命令整体INCOMPLETE，不是权限或全Session撤销PASS。
- Changed/Files：先CR-AUT006；新增纯`domain/user_state.py`决策与不可变`application/user_state_result.py`首响应DTO、9项unit。
- Tests：Windows11/Python3.13.15后端1328项无失败，2项既有符号链接权限跳过。九新unit覆盖启停精确动作/版本/Session要求、同状态不造no-op、stale/溢出、最后Admin保护/有其他Admin不全面禁止Admin目标、无凭据不能启用、类型/坏源拒绝、DTO自停用来源可表达/不可变/安全字段、状态计数版本时间严格及nested tamper重核。
- Migration/API：无新Schema/migration/HTTP/权限接线/依赖；head仍0046。仅设计计划0047，不表示已升级。
- Build：开发wheel708803字节，SHA256 `d224377d4a60adb4e7e4b9bc87221a1ef49219d7fc54615b4c3d28ae4622a48d`；非安装包，不上传本地wheel。
- Known Issues：本轮真实PG/HTTP/权限集成/状态并发未运行，因尚无状态持久层；最后Admin计数和Session必须实际锁定来源，纯Domain不证明安全。状态Schema/App/原子全Session/自停用末核/HTTP/Windows/正式供给/性能/三平台/UI/完整包待。
- Next：AUT-04-A11-P02按CR-AUT006新增独立statefirst ORM/0047，真实空/有数据upgrade/down/来源/历史及非空降级拒绝验证；其后P03原子命令，CR/Gate不关闭。
