#!/usr/bin/env python3
"""
Check BabelDOC version and imports for compatibility
"""

def check_babeldoc_compatibility():
    """Check if BabelDOC is compatible with our code"""
    try:
        import babeldoc
        version = babeldoc.__version__
        print(f"✅ BabelDOC version: {version}")
        
        # Check if version is in supported range
        from packaging import version as pkg_version
        
        min_version = "0.3.64"
        max_version = "0.4.0"
        
        if pkg_version.parse(version) >= pkg_version.parse(min_version) and \
           pkg_version.parse(version) < pkg_version.parse(max_version):
            print(f"✅ Version {version} is in supported range ({min_version} <= version < {max_version})")
        else:
            print(f"⚠️  Version {version} may not be compatible (expected: {min_version} <= version < {max_version})")
        
        # Try to import required modules
        try:
            from babeldoc.high_level import async_translate
            print("✅ babeldoc.high_level.async_translate imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import babeldoc.high_level.async_translate: {e}")
            
            # Try alternative import paths for newer versions
            alternatives = [
                ("babeldoc.translate", "translate"),
                ("babeldoc.api", "translate"),
                ("babeldoc.core", "translate"),
            ]
            
            for module_path, func_name in alternatives:
                try:
                    module = __import__(module_path, fromlist=[func_name])
                    if hasattr(module, func_name):
                        print(f"💡 Alternative found: {module_path}.{func_name}")
                        return True
                except ImportError:
                    continue
            
            return False
        
        try:
            from babeldoc.main import create_progress_handler
            print("✅ babeldoc.main.create_progress_handler imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import babeldoc.main.create_progress_handler: {e}")
            return False
            
        try:
            from babeldoc.translation_config import TranslationConfig
            print("✅ babeldoc.translation_config.TranslationConfig imported successfully")
        except ImportError as e:
            print(f"❌ Failed to import babeldoc.translation_config.TranslationConfig: {e}")
            return False
        
        print("🎉 All BabelDOC imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ BabelDOC import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    import sys
    if check_babeldoc_compatibility():
        print("✅ BabelDOC is compatible")
        sys.exit(0)
    else:
        print("❌ BabelDOC compatibility check failed")
        sys.exit(1)