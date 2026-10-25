# PLT-PKG-01-A09-P17：Windows隔离安装布局装配

日期：2026-10-01；状态：`NON_RELEASE_ISOLATED_LAYOUT_PASS / FORMAL_INSTALL_BLOCKED`。

编码前检查：Phase2/Gate3开放；输入为P15固定非发行ZIP、P16只读门禁、ADR-013和示例配置。只新增离线候选到临时安装布局的显式映射、全量Hash与安全启动前探针；实体/API/权限/Migration不变。验收：源ZIP与清洁暂存21,103项一致，目标只允许新的ASCII Temp直属目录，逐件复制/回读，模型指纹和嵌入式/原生版本、三个服务`PLAN_ONLY`通过；`C:\PLMTool`、SCM和数据库不得改变。风险是临时布局不具目标账户/ACL/License/HTTPS；回滚弃用本轮临时目录/工具即可，不触碰历史ZIP。

DEC-20261001-565预先记录了路径映射。候选的`payload/ocr/models`映射为安装模板要求的`app/models`，其他族映射至`runtime/python`、`runtime/pgsql`、`app/frontend`、`app/ocr`、`config`和`app/third-party-licenses`。安装元数据原字节保留在`app/package-metadata`。合成`config/bootstrap.rehearsal.yaml`只引用新临时目录的空`data`和已核模型，不含MAC、密码、Key、数据库URL或客户资料；不是正式配置。`plugins/data/logs/license`只创建空目录。

首次尝试因先前对P15暂存目录的Python导入产生3,312个`__pycache__`附加文件，源完整文件集检查正确拒绝；源ZIP未变。重新从固定ZIP解包到新ASCII目录并21,103/21,103验Hash。第二次尝试在目标回读阶段发现新工具误将目标路径作为源索引，完整复制后拒绝；修正后在另一个全新目标目录重跑，不复用失败目录。最终隔离布局`C:\Users\17231\AppData\Local\Temp\plm-install-rehearsal-38b12260d10a`：21,103件逐件复制/目标读盘及源末次Hash PASS；模型指纹`511580fe3e72fe1759ce18ac05d5454eee88865303603631be644a4978889cf4`匹配；嵌入式Python应用版本0.1.0.dev0及主要模块导入、PG18.6、Tesseract5.5.3、Ghostscript10.08.0、三服务只读命令计划均通过。探针使用`-B`避免在目标产生pyc，检查额外pycache/pyc为0；单元2/2。

未调用SCM、未启动API/Worker/PG、未运行Migration或OCR真实质量，不代表可使用安装。正式License/签名、第三方完整NOTICE/对应源码/公开合规、目标账户及ACL/HTTPS、备份升级、Server2025产品安装与Gate仍开放；Debian13按用户指令暂缓实机验证。下一项应在该隔离布局运行可逆的纯合成整机启动前链（临时PG、配置加载、后端HTTP/前端静态资源），同时保持正式安装/发行门禁关闭。
