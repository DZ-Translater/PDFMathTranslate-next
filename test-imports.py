#!/usr/bin/env python3
"""
Test script to verify all imports work correctly
"""

import sys

def test_import(module_name, import_path=None):
    """Test importing a module"""
    try:
        if import_path:
            exec(f"from {module_name} import {import_path}")
            print(f"✅ {module_name}.{import_path} imported successfully")
        else:
            exec(f"import {module_name}")
            print(f"✅ {module_name} imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Failed to import {module_name}: {e}")
        return False
    except Exception as e:
        print(f"❌ Error importing {module_name}: {e}")
        return False

def main():
    print("🔍 Testing critical imports...")
    
    success = True
    
    # Test basic imports
    success &= test_import("fastapi")
    success &= test_import("uvicorn")
    success &= test_import("pydantic")
    success &= test_import("pathlib", "Path")
    
    # Test babeldoc imports
    success &= test_import("babeldoc")
    success &= test_import("babeldoc.high_level", "async_translate")
    success &= test_import("babeldoc.main", "create_progress_handler")
    success &= test_import("babeldoc.translation_config", "TranslationConfig")
    
    # Test pdf2zh_next imports
    success &= test_import("pdf2zh_next.config", "ConfigManager")
    success &= test_import("pdf2zh_next.config.cli_env_model", "CLIEnvSettingsModel")
    success &= test_import("pdf2zh_next.config.model", "SettingsModel")
    success &= test_import("pdf2zh_next.high_level", "do_translate_async_stream")
    
    if success:
        print("\n🎉 All imports successful!")
        return 0
    else:
        print("\n❌ Some imports failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())