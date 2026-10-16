# AUT-05-A02 登录页面测试报告

2026-09-27；0.1.0.dev0；Windows11 Node24.17.0/pnpm11.19.0。

最终前端完整63/63 PASS、vue-tsc/tsc PASS、Vite build PASS；36modules、JS100160bytes、CSS4124bytes，页面及客户端已引用。新增11用例覆盖label/无自动Auth、成功清密码与Token不入DOM、受限提示/不展示管理、GET重登/禁写、真实client续期及logout Key/确认、网络故障不冒充退出、pending重复submit/即时清密码、卸载丢弃响应、路由/404、显示字符串HTML逃逸、AppShell真实/login路由。

初轮61测试5失败来自Vue递归代理SessionClient而JS私有字段brand不匹配，实际fetch0；用toRaw解包修复，完整61后补两项并最终63复验通过。不是服务端或密码验证故障，不删除私有字段或放松安全检查。

全部成功fetch模拟，尚未验证真实服务器Cookie/CSRF、浏览器可视布局/网络流程、HTTPS/正式材料/生产部署；本批后端unit/PG/coverage/HTTP性能/wheel未运行。无后端/DB/Migration/API/依赖变更，兼容0049，无升级。改密/开发Auth代理尚待，CR008 FAIL/Gate/完整包保留。
