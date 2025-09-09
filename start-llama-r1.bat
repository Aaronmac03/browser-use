@echo off
REM DeepSeek R1 8B Model Launcher with GPU Optimization
REM Optimized for GTX 1660 Ti (6GB VRAM)

echo [INFO] Starting DeepSeek R1 Distill Llama 8B with GPU acceleration...
echo [INFO] Model: deepseek-r1-distill-llama-8b-q4_k_m.gguf

REM Set model environment variable
set MODEL_NAME=r1

REM Call the main GPU startup script
call "%~dp0start-llama-gpu.bat"