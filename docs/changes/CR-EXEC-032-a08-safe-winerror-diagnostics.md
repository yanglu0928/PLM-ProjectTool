# CR-EXEC-032：SUR-07-A08 WinError 脱敏诊断补齐

日期：2026-11-07  
状态：实施前记录；A08 未通过。

## 证据

GitHub Hosted workflow run [42259742947](https://github.com/yanglu0928/PLM-ProjectTool/actions/runs/42259742947) 的 A08 packaged SurveyVersion Edge HTTPS PostgreSQL flow job 在 Windows Server 2025 Hosted runner 上，通过同 run A17 非发行候选下载及身份校验、D盘目录边界和语法检查。随后包内验收 exit=1、无 A08 业务通过标记。安全摘要显示异常类别 WinError、末帧 <frozen ntpath>:709、last_stage=none。原始验收器输出未上传，D盘临时根按所有权清理。

该摘要没有 WinError 数值和业务阶段，无法判断错误源于路径操作、子进程、浏览器或产品业务。不得据此修改产品或宣布 WBS 通过。

## 单点变更

仅修改 validation/sur-07-a08-survey-version-packaged/verify.py 与其 A08 Workflow 包装诊断：

- 验收器在 smoke 入口、浏览器验收入口和关键回调边界写出固定阶段枚举；
- 捕获失败时输出异常类型、整数 WinError（若存在）和最多 8 个 traceback basename:line；排除异常消息、绝对/相对路径、请求/响应、客户数据、环境变量与日志正文；
- Workflow 只提取符合严格字符/长度白名单的该诊断字段，成功标记与所有原断言保持不变；
- 不改产品、API、Schema、数据库、权限、正式信任与验收门槛。

## 风险与回滚

风险：有限调用栈仍可能只显示路径库末帧；阶段枚举能补充调用阶段。诊断不得用于放宽验收。回滚仅还原 A08 验收器和 Workflow 的诊断增量，不改已生成产品包内容或基线。

## 验证计划与数据边界

在 GitHub Hosted Windows Server 2025 runner 的 D盘运行；同 run、非发行候选，隔离 PG18、真实 Edge/HTTPS、仅合成一次性项目/用户/调研数据。验证必须继续通过三个既有标记：A08 PG、A12 P05 Edge 与 A08 License denial。原始输出不上传，测试目录仅清理精确 owned 根。不在用户本机或 C盘运行项目代码，不外发客户资料、不调用外部 AI、不执行插件。
