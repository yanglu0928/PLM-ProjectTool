# PLT-PKG-01-A09-P51-A42：离线暂存安装文件签名门禁结果

- 日期：2026-11-02
- 状态：PASS_LIMITED
- Workflow：[GitHub hosted Windows run 41370763918](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/41370763918)

## 结果

- 暂存CLI增加 `--installer` 与 `--expected-thumbprint`；必须同时提供。
- 有效系统签名和匹配的外部指纹通过验签，回执标记 `AUTHENTICODE_VERIFIED_TEST_ONLY`。
- 错误指纹在ZIP暂存之前拒绝，目标目录未创建；缺少参数配对也有定向测试。
- 26项Windows hosted定向测试、真实签名/错误pin集成、A35父包20,119文件暂存和A38/BLOCKED诊断全部通过。
- 全程未执行安装器、未安装或启动产品；未写用户机器。

## 限制

验证使用hosted系统签名文件作为测试签名正例，不能替代真实产品证书或正式外部指纹。结果不构成生产信任、Windows 11实机、Pilot、Gate 3或Release通过。
