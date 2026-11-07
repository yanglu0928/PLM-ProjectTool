# PLT-PKG-01-A09-P51-A37：Windows Pilot 非秘密输入登记验证结果

- 日期：2026-10-30
- 状态：PASS_LIMITED（Windows 11 Home build 26300；仅空白/合成登记值验证）
- 前置检查：`plt-pkg-01-a09-p51-a37-input-register-precheck.md`
- 上一项：A36 PASS_LIMITED；真实信任与运行前置尚无正式输入。

## 交付

- `tools/validate_windows_pilot_input_register.py`：Python 标准库只读验证器。只接受固定结构和有限格式的非秘密引用；拒绝额外字段及格式错误。CLI 只打印固定状态、固定错误码和白名单字段名，不回显输入值、路径或未知键；不修改登记文件。
- `docs/templates/windows-pilot-input-register.template.json`：所有正式材料引用均为空，仅保留冻结的数据库 Credential Manager 目标名。
- `docs/deployment/windows-pilot-input-register.md`：登记范围、仓库外受控存放约定、运行方法和状态解释。
- 不接入产品启动器/manifest、不读取凭据或私钥、不代表 License/证书/服务/数据库验收，也不产生 Pilot Ready 结论。

## 验证结果

- Windows 11 Home build 26300，本机 Python 3.13，`tools/tests/test_validate_windows_pilot_input_register.py`：6/6 通过（0.147秒）。涵盖空模板、完整元数据仍需独立验证、额外疑似私钥字段不回显、非法引用不回显、非整数版本拒绝、CLI仅输出安全状态和字段名。
- TEMP/TMP/RUNNER_TEMP/Python cache 均指向 `D:\\A35Temp`；仓库与测试源码位于 D 盘。
- 首轮测试夹具将证据编号生成成含下划线的形式，与已登记编号语法不一致，测试失败。修正为约定的连字符格式，并增加版本号必须为整数的负例；最终6/6通过。没有放宽编号规则。
- 没有接触用户密钥、Credential Manager 内容、客户资料、服务、数据库或 C 盘；测试输入为合成值。

## 限制与后续

记录完整仅说明引用结构齐全，不能证明引用内容真实性。真实公钥/License绑定、数据库目标账户范围、Windows服务身份/ACL和TLS证书链/续期仍须独立验证。Pilot、Gate 3～7及正式Release不变，继续NOT_READY。
