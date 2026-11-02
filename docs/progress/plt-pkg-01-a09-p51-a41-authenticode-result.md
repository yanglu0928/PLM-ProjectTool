# PLT-PKG-01-A09-P51-A41：Windows Authenticode 只读校验器结果

- 日期：2026-11-02
- 状态：PASS_LIMITED
- 验收环境：GitHub hosted Windows Server 2025；未在用户本机运行。
- Workflow：[run 41370436650](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370436650)
- 代码：`tools/verify_windows_authenticode.py`

## 验收

- 24项定向回归全部通过，其中5项覆盖签名状态、发布者指纹、无效输入、PowerShell失败和畸形输出。
- hosted Windows 实际调用原生 Authenticode：有效系统签名且外部指纹匹配时通过；D盘临时未签名脚本被拒绝。
- 只读校验，不执行待查文件、不修改证书存储、不联网；拒绝结果不回显路径。
- A40候选暂存同一run复验通过，20,119文件暂存及5项启动阻断维持不变。

## 限制与后续

返回值明确为 `AUTHENTICODE_VERIFIED_TEST_ONLY`。真实产品签发者证书/包外正式指纹尚未提供，当前工具不能作为产品安装授权或正式发布信任证明。此项不安装产品、不启动服务，不构成Windows 11、Pilot、Gate 3或正式Release验收。

下一项A42将校验器接入候选安装文件的暂存前置，并验证无签名或指纹不匹配时不会生成可执行落地结果。
