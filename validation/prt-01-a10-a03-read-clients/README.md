# PRT-01-A10-A03 Prototype read-client verification

Run on the supported Windows 11 development environment:

```powershell
pwsh -File validation/prt-01-a10-a03-read-clients/verify.ps1
```

The harness verifies all five read-client families and nine frozen GET paths, then runs the complete frontend suite,
TypeScript/Vue type checking, and the production build. Success ends with
`PRT_01_A10_A03_READ_CLIENTS_PASS`.
