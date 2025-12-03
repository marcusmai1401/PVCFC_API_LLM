#!/usr/bin/env python3
"""
Patch static_infer.py to enable PIR mode for .json models (PP-OCRv5)
This fixes the RuntimeError with PaddlePaddle 3.0 and PIR models
"""

import re
from pathlib import Path

# Path to the file that needs patching
STATIC_INFER_PATH = Path(
    r"C:\Users\Admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\paddlex\inference\models\common\static_infer.py"
)


def patch_static_infer():
    """Apply comprehensive PIR-aware patches to static_infer.py"""

    print(f"📂 Reading file: {STATIC_INFER_PATH}")
    with open(STATIC_INFER_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup if not already done
    backup_path = STATIC_INFER_PATH.with_suffix(".py.backup_original")
    if not backup_path.exists():
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Created backup: {backup_path}")

    # ===== PATCH 1: Add is_pir_model detection after config creation =====
    print("\n🔧 PATCH 1: Adding PIR model detection...")

    # Find the line where config is created (line 383)
    pattern1 = r"(\s+)config = paddle\.inference\.Config\(str\(model_file\), str\(params_file\)\)\n"
    replacement1 = r'\1config = paddle.inference.Config(str(model_file), str(params_file))\n\1is_pir_model = str(model_file).endswith(".json")\n'

    content, n1 = re.subn(pattern1, replacement1, content, count=1)
    if n1 > 0:
        print(f"  ✓ Added is_pir_model detection ({n1} location)")
    else:
        print(f"  ⚠ Warning: Pattern not found for config creation")

    # ===== PATCH 2: Replace all enable_new_ir(False) with conditional logic =====
    print("\n🔧 PATCH 2: Making enable_new_ir conditional...")

    pattern2 = r'(\s+)if hasattr\(config, "enable_new_ir"\):\n\1    config\.enable_new_ir\(False\) # Explicitly disable'
    replacement2 = r"""\1if hasattr(config, "enable_new_ir"):
\1    if is_pir_model:
\1        config.enable_new_ir(True)
\1    else:
\1        config.enable_new_ir(False)  # Explicitly disable"""

    content, n2 = re.subn(pattern2, replacement2, content)
    print(f"  ✓ Updated enable_new_ir calls ({n2} locations)")

    # ===== PATCH 3: Enable new_executor for PIR models =====
    print("\n🔧 PATCH 3: Enabling new_executor for PIR models...")

    # Replace commented enable_new_executor with conditional version
    pattern3 = r'(\s+)# if hasattr\(config, "enable_new_executor"\):\n\1#     config\.enable_new_executor\(\)'
    replacement3 = r'\1if hasattr(config, "enable_new_executor") and is_pir_model:\n\1    config.enable_new_executor()'

    content, n3 = re.subn(pattern3, replacement3, content)
    print(f"  ✓ Updated enable_new_executor calls ({n3} locations)")

    # ===== PATCH 4: Make IR optimization conditional =====
    print("\n🔧 PATCH 4: Making IR optimization PIR-aware...")

    # Find the section around lines 475-480
    pattern4 = r'(\s+)# Temporarily disable IR optimization to fix "op \[\] kernel output args \(0\) defs should equal op outputs \(1\)" error\.\n\1if hasattr\(config, "switch_ir_optim"\):\n\1    config\.switch_ir_optim\(False\)\n\n\1# Force disable all optimization to avoid the RuntimeError related to op kernel output args\.\n\1config\.set_optimization_level\(0\)'

    replacement4 = r"""\1# Configure IR optimization and level based on model format
\1if is_pir_model:
\1    # PIR models (.json): Enable IR optimizations
\1    if hasattr(config, "switch_ir_optim"):
\1        config.switch_ir_optim(True)
\1    # Keep default optimization level for PIR
\1else:
\1    # Legacy models: Disable IR optimization to fix op kernel output args errors
\1    if hasattr(config, "switch_ir_optim"):
\1        config.switch_ir_optim(False)
\1    # Force disable all optimization to avoid RuntimeError
\1    config.set_optimization_level(0)"""

    content, n4 = re.subn(pattern4, replacement4, content)
    if n4 > 0:
        print(f"  ✓ Updated IR optimization logic ({n4} location)")
    else:
        print(
            f"  ⚠ Warning: IR optimization pattern not found (might need manual check)"
        )

    # ===== Write patched content =====
    print(f"\n💾 Writing patched file...")
    with open(STATIC_INFER_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Successfully patched: {STATIC_INFER_PATH}")
    print(f"\n📊 Summary:")
    print(f"  - PIR detection added: {'✓' if n1 > 0 else '✗'}")
    print(f"  - enable_new_ir updated: {n2} locations")
    print(f"  - enable_new_executor updated: {n3} locations")
    print(f"  - IR optimization logic updated: {'✓' if n4 > 0 else '⚠'}")

    return True


if __name__ == "__main__":
    try:
        success = patch_static_infer()
        if success:
            print("\n🎉 Patch completed successfully!")
            print("\n📝 Next steps:")
            print("  1. Clear Python cache: del __pycache__ folders")
            print("  2. Run: python .\\verify_v5.py")
    except Exception as e:
        print(f"\n❌ Error during patching: {e}")
        print(f"\n🔄 To restore backup:")
        print(f"   Copy: {STATIC_INFER_PATH}.backup_original")
        print(f"   To:   {STATIC_INFER_PATH}")
        raise
