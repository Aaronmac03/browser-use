# Ollama Setup & Model Migration Guide

## Quick Setup (Recommended)

For the easiest setup experience, run:

```bash
python setup_ollama.py
```

This will automatically:
- Check if Ollama is installed
- Start the service if needed  
- Pull the required `moondream:latest` model
- Remove old MiniCPM-V models to free space
- Verify everything is working

## Manual Setup

If you prefer manual setup or the automatic setup fails:

### 1. Install Ollama
- **Windows**: Download from https://ollama.ai or `winget install Ollama.Ollama`
- **macOS**: Download from https://ollama.ai or `brew install ollama`
- **Linux**: `curl -fsSL https://ollama.ai/install.sh | sh`

### 2. Start Ollama Service
```bash
ollama serve
```

### 3. Install Required Model
```bash
ollama pull moondream
```

### 4. Remove Old Models (Optional)
```bash
# Free up disk space by removing old MiniCPM-V models
ollama rm minicpm-v
ollama rm minicpm-v:latest  
ollama rm openbmb/minicpm-v2.6
```

### 5. Verify Setup
```bash
# Check health and model availability
python ollama_manager.py --health

# Or list models manually
ollama list
```

## Advanced Management

For advanced Ollama management, use the dedicated manager:

```bash
# Complete setup with cleanup
python ollama_manager.py --setup

# Health check only
python ollama_manager.py --health

# Use custom model
python ollama_manager.py --setup --model moondream:latest
```

## Files Updated

The following files have been updated to use `moondream:latest`:

- `hybrid_agent.py` - Main agent configuration
- `vision_module.py` - Vision analysis module  
- `test_vision.py` - Test scripts
- `aug25.md` - Documentation
- `hybrid_brief.md` - Technical brief
- `phase1_summary.md` - Phase summary

## New Files Added

- `ollama_manager.py` - Comprehensive Ollama management
- `setup_ollama.py` - Quick setup script
- This updated guide

## Troubleshooting

**Q: The hybrid agent exits immediately saying "Ollama not configured"**
A: Run `python setup_ollama.py` to automatically fix the setup

**Q: Vision analysis fails with connection errors**  
A: Ensure Ollama service is running: `ollama serve`

**Q: Model not found errors**
A: Pull the required model: `ollama pull moondream`

**Q: Out of disk space**
A: Remove old models: `python ollama_manager.py --setup` (includes cleanup)

The hybrid agent now **requires** a working Ollama setup to function - it will not start with degraded vision capabilities.