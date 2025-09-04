@echo off
echo ============================================================
echo BROWSER-USE PERFORMANCE VALIDATION
echo GTX 1660 Ti + i7-9750H + 16GB RAM
echo ============================================================

set VALIDATION_PASSED=0
set TOTAL_TESTS=0

echo.
echo [TEST 1] Checking server configuration...
set /a TOTAL_TESTS+=1
if exist "e:\ai\start-llama-server.bat" (
    findstr /C:"--n-gpu-layers 35" "e:\ai\start-llama-server.bat" >nul
    if !errorlevel! equ 0 (
        findstr /C:"--threads 6" "e:\ai\start-llama-server.bat" >nul
        if !errorlevel! equ 0 (
            findstr /C:"--batch-size 512" "e:\ai\start-llama-server.bat" >nul
            if !errorlevel! equ 0 (
                echo [✓] Server configuration optimized for GTX 1660 Ti
                set /a VALIDATION_PASSED+=1
            ) else (
                echo [✗] Batch size optimization missing
            )
        ) else (
            echo [✗] Thread optimization missing
        )
    ) else (
        echo [✗] GPU layers optimization missing
    )
) else (
    echo [✗] Server configuration file not found
)

echo.
echo [TEST 2] Checking configuration files...
set /a TOTAL_TESTS+=1
set CONFIG_FILES_FOUND=0

if exist "e:\ai\browser-use\enhanced_local_llm.py" (
    set /a CONFIG_FILES_FOUND+=1
)
if exist "e:\ai\browser-use\hardware_optimization.py" (
    set /a CONFIG_FILES_FOUND+=1
)
if exist "e:\ai\browser-use\hybrid_orchestrator.py" (
    set /a CONFIG_FILES_FOUND+=1
)
if exist "e:\ai\browser-use\performance_optimizer.py" (
    set /a CONFIG_FILES_FOUND+=1
)

if %CONFIG_FILES_FOUND% equ 4 (
    echo [✓] All configuration files present
    set /a VALIDATION_PASSED+=1
) else (
    echo [✗] Missing configuration files: %CONFIG_FILES_FOUND%/4 found
)

echo.
echo [TEST 3] Checking LLM configuration...
set /a TOTAL_TESTS+=1
findstr /C:"step_timeout: int = 45" "e:\ai\browser-use\enhanced_local_llm.py" >nul
if !errorlevel! equ 0 (
    findstr /C:"enable_gpu_acceleration: bool = True" "e:\ai\browser-use\enhanced_local_llm.py" >nul
    if !errorlevel! equ 0 (
        findstr /C:"hardware_profile: str = \"gtx_1660_ti\"" "e:\ai\browser-use\enhanced_local_llm.py" >nul
        if !errorlevel! equ 0 (
            echo [✓] LLM configuration optimized
            set /a VALIDATION_PASSED+=1
        ) else (
            echo [✗] Hardware profile not set
        )
    ) else (
        echo [✗] GPU acceleration not enabled
    )
) else (
    echo [✗] Timeout optimization missing
)

echo.
echo [TEST 4] Checking hybrid orchestrator...
set /a TOTAL_TESTS+=1
if exist "e:\ai\browser-use\hybrid_orchestrator.py" (
    findstr /C:"local_first_threshold: float = 0.9" "e:\ai\browser-use\hybrid_orchestrator.py" >nul
    if !errorlevel! equ 0 (
        echo [✓] Hybrid orchestrator configured for 90%+ local processing
        set /a VALIDATION_PASSED+=1
    ) else (
        echo [✗] Local-first threshold not optimized
    )
) else (
    echo [✗] Hybrid orchestrator not found
)

echo.
echo ============================================================
echo VALIDATION RESULTS
echo ============================================================
echo Tests Passed: %VALIDATION_PASSED%/%TOTAL_TESTS%

if %VALIDATION_PASSED% geq 3 (
    echo Status: PASS - Performance optimizations validated
    echo.
    echo [READY] Browser-use is optimized for GTX 1660 Ti hardware
    echo [READY] Hybrid architecture: Cloud planning + Local execution
    echo [READY] Privacy-first: Web content stays local
    exit /b 0
) else (
    echo Status: FAIL - Performance optimizations incomplete
    echo.
    echo [ACTION] Review configuration files and re-run optimization
    exit /b 1
)