# Backend tests

测试目录固定分为 `unit`、`contract`、`integration`、`permission` 和 `architecture`，并在需要时按模块名镜像。测试不得通过跨模块 ORM fixture 绕过 Application Port。
