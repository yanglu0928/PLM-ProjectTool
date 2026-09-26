# Windows 11 Ghostscript 安装证据

## Environment

- Windows 11 Home 10.0.26200 x86-64。
- Ghostscript 10.08.0 x64。
- 安装模式：项目内 portable，不写入系统目录，不要求管理员权限。

## Input

- 官方安装包：`gs10080w64.exe`。
- 官方 SHA-256：`52a91b8bf09298788d7a57b9206127026c23eacd75405f0a131e26dc381dce50`。
- 可重复安装脚本：`scripts/windows/install-ghostscript-portable.ps1`。

## Steps

1. 从 Ghostscript 官方 GitHub Release 下载 Windows x64 安装包。
2. 校验安装包 SHA-256。
3. 使用 7-Zip 将 NSIS 安装包展开到项目忽略的 `artifacts` 目录。
4. 执行 `gswin64c.exe --version`。
5. 将 Ghostscript 加入当前 PoC 进程 PATH，执行 OCRmyPDF PDF/A-2b 验证。

## Result

- Ghostscript 返回版本 `10.08.0`。
- OCRmyPDF 成功发现 Ghostscript。
- PDF/A-2b 输出验证通过。
- 结果：PASS。

## Metrics

|指标|结果|
|---|---|
|安装包 Hash|PASS|
|可执行文件版本|10.08.0|
|安装权限|无需管理员权限|
|PDF/A-2b 转换|PASS|

## Logs

- OCRmyPDF 日志：`ocrmypdf-stderr.txt`。
- 综合结果：`result.json`。
- 安装脚本会输出版本、可执行文件、安装包 Hash 和安装模式 JSON。

## Known Issues

1. portable 安装依赖 7-Zip 解包；脚本会在系统无 7-Zip 时校验并展开官方 7-Zip MSI。
2. `artifacts` 中的本机安装文件不进入 Git，正式离线发行包仍需在 Release Gate 生成和验收。
3. 当前仓库尚未公开，AGPL 对外发行条件尚未完成；见 ADR-002。

## Conclusion

Ghostscript 10.08.0 已在 Windows 11 完成可重复的项目内安装，并通过 OCRmyPDF PDF/A-2b 最小功能验证。

## PASS / FAIL

`PASS`

## Alternative

若未来不采用源码公开策略，则必须改用 Ghostscript 商业许可；当前不执行该替代方案。
