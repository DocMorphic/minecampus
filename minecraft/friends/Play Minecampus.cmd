@echo off
setlocal
cd /d "%~dp0"
if not exist "%~dp0launcher\prismlauncher.exe" goto missing
if not exist "%~dp0data\instances\minecampus\mmc-pack.json" goto missing
start "" "%~dp0launcher\prismlauncher.exe" --dir "%~dp0data" --launch minecampus
exit /b
:missing
echo First right-click the downloaded ZIP and choose Extract All.
echo Then open Play Minecampus from the extracted folder.
pause
exit /b 1
