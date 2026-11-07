# Windows Pilot 非秘密输入登记约定

登记表只接收引用元数据，不保存 License 正文、数据库口令、私钥、证书私钥、API Key 或文件内容。请把实际填写文件放在项目仓库和 GitHub 之外的受控位置，再把本地文件路径传给验证工具。验证器不会改写输入，也不会输出文件路径、登记值或未识别字段名。

使用 `docs/templates/windows-pilot-input-register.template.json` 作为空白模板，填写规则如下：

| 字段 | 可登记内容 |
|---|---|
| `product_public_key_sha256` | 正式产品公钥文件的 SHA-256 指纹；不登记公钥/私钥正文 |
| `license_evidence_ref` | 指向受控 License 验收证据的编号 |
| `database_credential_target` | 固定为 `PLMProjectTool/Database`，仅表示 Credential Manager 目标名 |
| `service_identity_ref` | 受控 Windows 虚拟服务账户标识，如 `NT SERVICE\PLMProjectTool` |
| `tls_certificate_thumbprint` | 证书指纹，不登记证书或私钥 |
| `tls_dns_name` | 证书要覆盖的 DNS 名 |
| `evidence_refs.*` | 对应 License、服务 ACL、TLS 链/续期及数据库范围证据编号 |

运行：

```powershell
py -3.13 tools\validate_windows_pilot_input_register.py --input "D:\受控目录\windows-pilot-input-register.json"
```

输出状态含义：

- `INCOMPLETE`：存在空引用。输出只列出固定字段名。
- `INVALID`：JSON 结构、字段、类型或格式不符合约定。不会回显输入内容。
- `COMPLETE_REQUIRES_INDEPENDENT_VERIFICATION`：引用元数据完整；仍不代表 License/数据库/服务/TLS 已通过验证，也不会放行产品启动。

完整登记后，仍须分别验证真实公钥与 License 绑定、当前服务身份及 ACL、指定数据库目标凭据与连接范围、证书主机名/有效期/CA 链/轮换策略。不要把登记文件、真实密钥或凭据上传到 GitHub Artifact、日志或源代码。
