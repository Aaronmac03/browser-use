# 🗑️ Files Safe to Delete

This document lists files that can be safely deleted now that we have the centralized model configuration system.

## ✅ **HIGH CONFIDENCE - Delete These First**

### Test Files (Obsolete/Duplicate)
```bash
rm browser-agent/test_enhanced_routing.py           # Marked as obsolete in code
rm browser-agent/test_simplified_routing.py        # Tests deprecated architecture  
rm browser-agent/debug_models.py                   # Temporary debug script
rm browser-agent/debug_planning_detection.py       # Temporary debug script
rm browser-agent/temp_test_requirements.txt        # Temporary file
```

**Reason**: These files test old routing systems or are temporary debugging artifacts.

## ⚠️ **MEDIUM CONFIDENCE - Review Dependencies First**

### Configuration Files (Superseded)
```bash
# Check imports first, then delete:
rm browser-agent/config/enhanced_models.py         # Superseded by central_model_config.py
```

**Reason**: This file provided the old three-tier model configuration that's now in the centralized config.

### Test Files (Redundant)
```bash
# After verifying functionality is covered elsewhere:
rm browser-agent/test_config_basic.py             # Basic config testing
rm browser-agent/test_classifier_only.py          # Isolated component test
```

**Reason**: Functionality is covered by `test_centralized_config.py` and other comprehensive tests.

## 🔍 **LOW CONFIDENCE - Requires Code Review**

### Legacy Configuration (Major Dependencies)
```bash
# ONLY after updating all imports throughout codebase:
# rm browser-agent/config/models.py               # Original model configuration
```

**Reason**: This file is still widely referenced. Need to update all imports first.

### Model Router (Architecture Decision)
```bash
# ONLY if logic has been moved to central config:
# rm browser-agent/models/enhanced_model_router.py
```

**Reason**: This might still contain useful logic not yet moved to centralized config.

## 📋 **Deletion Commands**

### Phase 1: Safe Deletions (Run Now)
```bash
cd browser-agent

# Delete obsolete test files
rm test_enhanced_routing.py
rm test_simplified_routing.py 
rm debug_models.py
rm debug_planning_detection.py
rm temp_test_requirements.txt

echo "✅ Phase 1 cleanup complete - 5 files deleted"
```

### Phase 2: After Import Analysis
```bash
cd browser-agent

# Find all references to enhanced_models.py
echo "Checking references to enhanced_models.py..."
grep -r "enhanced_models" . --exclude-dir=__pycache__ || echo "No references found"

# If no critical references:
rm config/enhanced_models.py

# Check redundant test files
rm test_config_basic.py
rm test_classifier_only.py

echo "✅ Phase 2 cleanup complete - 3 more files deleted"
```

### Phase 3: Major Dependencies (Future)
```bash
# ONLY after updating all imports in the codebase:
# grep -r "from config.models import" . --exclude-dir=__pycache__
# grep -r "config.models" . --exclude-dir=__pycache__

# If all imports updated to use central_model_config:
# rm config/models.py

echo "⏳ Phase 3 requires import migration"
```

## 🔍 **How to Verify Safety**

Before deleting any file, run these checks:

### 1. Check for imports/references:
```bash
# Replace FILENAME with the file you want to delete
grep -r "FILENAME" . --exclude-dir=__pycache__ --exclude="*.pyc"
```

### 2. Check if it's imported by other files:
```bash
# For Python files, check for import statements
grep -r "from.*FILENAME import" . --exclude-dir=__pycache__
grep -r "import.*FILENAME" . --exclude-dir=__pycache__
```

### 3. Run tests after deletion:
```bash
python3 test_centralized_config.py
python3 test_flexible_config.py
```

## 📊 **Impact Summary**

| File | Size Impact | Risk | Dependencies |
|------|-------------|------|--------------|
| `test_enhanced_routing.py` | ~15KB | LOW | None (marked obsolete) |
| `test_simplified_routing.py` | ~12KB | LOW | Uses deprecated architecture |
| `debug_*.py` | ~5KB | LOW | Temporary files |
| `config/enhanced_models.py` | ~8KB | MEDIUM | Few references |
| `test_config_basic.py` | ~6KB | MEDIUM | Redundant functionality |
| `config/models.py` | ~20KB | HIGH | Many references |

**Total cleanup potential**: ~66KB across 8+ files

## ✅ **Benefits After Cleanup**

1. **Reduced Maintenance**: Fewer files to maintain and update
2. **Less Confusion**: No duplicate/outdated configurations  
3. **Cleaner Architecture**: Single source of truth is more obvious
4. **Faster Development**: Less code to search through

## 🚨 **Backup Recommendation**

Before deleting files, consider creating a backup:

```bash
# Create backup directory
mkdir -p ../backups/removed-files/$(date +%Y%m%d)

# Backup files before deletion
cp test_enhanced_routing.py ../backups/removed-files/$(date +%Y%m%d)/
cp config/enhanced_models.py ../backups/removed-files/$(date +%Y%m%d)/
# ... etc for other files

echo "✅ Backup created in ../backups/removed-files/$(date +%Y%m%d)/"
```

## 🎯 **Recommendation**

**Start with Phase 1** - these 5 files are definitely safe to delete and will provide immediate cleanup benefits with zero risk.