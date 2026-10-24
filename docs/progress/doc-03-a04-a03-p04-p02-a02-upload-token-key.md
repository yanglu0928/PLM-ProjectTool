# DOC-03-A04-A03-P04-P02-A02 独立上传 Token Windows 密钥

日期：2026-09-26；追溯：DEC-20260926-111、冻结 API-02 UploadIntent 短时 Token、既有 Windows 当前账户 Secret Key Lifecycle。

实现：固定独立引用 `document-upload-token-v1`，当前 Windows 账户凭据库只读，启动预检 32 字节；运行时 HMAC Token 签发仍重新解析该引用，失密失败关闭。不复用可信时间/Secret 主密钥/列表游标密钥，不自动生成正式材料。

验证：Windows 11/Python 3.13 后端 489 项无失败，2 项符号链接权限跳过；专用引用及缺钥/短钥拒绝、运行时失密拒绝；临时独立凭据删除后从加密备份恢复，旧上传 Token 与摘要可重新派生；开发 wheel 构建通过。测试引用已清理，不涉及用户或客户凭据。

升级：无 Migration、公开 API 或新依赖。回退为不装配上传路由；正式目标账户需在独立备份及口令保管就绪后由操作员供给，不能把本机合成密钥视为发行密钥。下一项 Windows 显式平台组合与真实 PostgreSQL Session/License/角色验证。
