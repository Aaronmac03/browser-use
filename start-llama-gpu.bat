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
echo [INFO] Model: qwen2.5-7b-instruct-q4_k_m.gguf
echo [INFO] GPU Layers: 35 (optimized for 6GB VRAM)
echo [INFO] Context Size: 2048 tokens (optimized for speed)
echo [INFO] Batch Size: 1024 (performance optimized)
echo [INFO] Performance: no-warmup + flash-attention enabled

llama-server.exe ^
    --model "E:\ai\llama-models\qwen2.5-7b-instruct-q4_k_m.gguf" ^
    --host localhost ^
    --port 8080 ^
    --ctx-size 2048 ^
    --batch-size 1024 ^
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