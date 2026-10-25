# PRT-01-A10-A04 Prototype write-client verification

Run on Windows 11:

```powershell
pwsh -File validation/prt-01-a10-a04-write-clients/verify.ps1
```

The harness verifies the Session write boundary, all five Prototype client families, the full frontend suite,
type checking, and the production build. Success ends with `PRT_01_A10_A04_WRITE_CLIENTS_PASS`.
