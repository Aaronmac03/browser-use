@echo off
REM GPU-Accelerated llama.cpp Server Startup Script for Windows PC
REM Optimized for i7-9750H + GTX 1660 Ti (6GB VRAM)
REM Author: Claude Code - Phase 3B Enhancement

echo [INFO] Starting GPU-Accelerated llama.cpp Server...
echo [INFO] Hardware: i7-9750H + GTX 1660 Ti (6GB VRAM)
echo [INFO] Models Directory: E:\ai\llama-models

REM Kill existing llama-server processes
echo [INFO] Stopping existing llama-server processes...
taskkill /f /im llama-server.exe >nul 2>&1
timeout /t 2 /nobreak >nul

REM Set environment variables for optimal performance
set CUDA_VISIBLE_DEVICES=0
set GGML_CUDA_ENABLE=1

REM Navigate to llama.cpp directory
cd /d "E:\ai\llama.cpp\build\bin\Release"

REM Start GPU-accelerated server with optimized settings for GTX 1660 Ti
echo [INFO] Starting llama-server with GPU acceleration...
echo [INFO] Model: qwen2.5-14b-instruct-q4_k_m.gguf
echo [INFO] GPU Layers: 35 (optimized for 6GB VRAM)
echo [INFO] Context Size: 65536 tokens (64K for browser-use prompts)
echo [INFO] Batch Size: 128 (memory optimized)
echo [INFO] Performance: no-warmup + flash-attention enabled

REM Default to Qwen 14B model, override with MODEL_NAME environment variable
if "%MODEL_NAME%"=="" set MODEL_NAME=qwen2.5-14b-instruct-q4_k_m.gguf
if "%MODEL_NAME%"=="r1" set MODEL_NAME=deepseek-r1-distill-llama-8b-q4_k_m.gguf

echo [INFO] Using model: %MODEL_NAME%

llama-server.exe ^
    --model "E:\ai\llama-models\%MODEL_NAME%" ^
    --host localhost ^
    --port 8080 ^
    --ctx-size 65536 ^
    --batch-size 128 ^
    --ubatch-size 256 ^
    --n-gpu-layers 35 ^
    --threads 4 ^
    --threads-batch 4 ^
    --memory-f16 ^
    --mlock ^
    --no-warmup ^
    --flash-attn ^
    --verbose

echo [ERROR] llama-server exited unexpectedly
pause