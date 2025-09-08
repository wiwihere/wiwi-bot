: : Opens vs-code in current directory
where code >nul 2>nul
if %errorlevel% neq 0 (
    pixi run code_insiders . | exit

) else (
    pixi run code . | exit
)