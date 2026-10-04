# AUT-04-A06：Windows User-list独立密钥来源

2026-09-27 Phase2编码前PASS。输入A05真实加密列表、现Windows Vault/交互供给/加密备份生命周期；仅只读KeyRef `user-list-cursor-v1`来源，缺失/长度错误/Provider异常静态失败，无明文环境fallback/运行时生成。无Schema/公开API/新依赖/角色，正式Key尚未供给、不挂列表。

DEC291：复用已验WindowsSecretKeyProvider/生命周期，User cursor保持独立用途，不用Job/Secret cursor key替代。实际Win11临时随机非正式引用测试失密/错误口令/防覆盖/原key恢复旧token，并清理仅本轮创建的凭据及临时备份；不得打印key/碰正式引用。后端和A05真HTTP/旧Windows详情回归，正式账户与其他账户/Server2025/性能/完整包/Gate待。回滚不用新入口保历史，供给与恢复沿原交互工具、备份不入Git。

执行结果：WINDOWS_LOCAL_KEY_SOURCE_PASS。新`entrypoints/windows_user_list_cursor.py`只读固定ref/严格32byte/静态错误；3新测试覆盖falsy真实Port不被替换、缺失/错shape/异常无fallback、实际随机临时Credential失密/错口令/防覆盖/原key恢复旧cipher与清理。1276后端无失败（2既有符号链接权限跳过），新增Win32测试实际执行，非跳过。A05实际PG多页HTTP/权限/五表无写与原文件发布回归通过。

开发wheel691195字节，SHA256 cbdf84c9858dc39601f96a322b0f7bdfb9a7716a3b348a55e7e665144e23cb66，非最终安装包。无Migration/API生产挂载/新依赖/角色/升级动作，0045兼容；正式引用未读写供给，正式账户应使用原交互工具独立供给及加密备份保管、不上传。当前平台尚未挂列表；下一A07装配会新增此必需信任源，缺失将拒绝启动，须明确记录兼容升级影响，不提供测试key回退。三平台/其他账户/性能/用户写/完整包/Gate待。
