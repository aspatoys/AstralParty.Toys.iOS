@echo off
rem 双击运行：先构建前端再启动界面。参数原样转给 start.ps1（例如 start.cmd -SkipBuild）。
setlocal
set "PS=pwsh"
where pwsh >nul 2>nul || set "PS=powershell"
"%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
set "code=%ERRORLEVEL%"
if not "%code%"=="0" pause
exit /b %code%
