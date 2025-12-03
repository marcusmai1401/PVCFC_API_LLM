from pathlib import Path

static_infer_path = Path(
    r"C:\Users\Admin\AppData\Local\Programs\Python\Python311\Lib\site-packages\paddlex\inference\models\common\static_infer.py"
)

# Read patched file
with open(static_infer_path, "r", encoding="utf-8") as f:
    content = f.read()

# Add is_pir_model check after config creation
old_line = "config = paddle.inference.Config(str(model_file), str(params_file))"
new_line = (
    "config = paddle.inference.Config(str(model_file), str(params_file))\n            is_pir_model = str(model_file).endswith("
    ".json"
    ")"
)

content = content.replace(old_line, new_line)

# Replace all enable_new_ir(False) with dynamic logic
old_pattern = "config.enable_new_ir(False) # Explicitly disable"
new_pattern = """if is_pir_model:
                    config.enable_new_ir(True)
                else:
                    config.enable_new_ir(False) # Explicitly disable"""

content = content.replace(old_pattern, new_pattern)

# Enable new_executor for PIR models
old_executor = '# if hasattr(config, ""enable_new_executor""):\n                #     config.enable_new_executor()'
new_executor = 'if hasattr(config, ""enable_new_executor"") and is_pir_model:\n                    config.enable_new_executor()'

content = content.replace(old_executor, new_executor)

# Write back
with open(static_infer_path, "w", encoding="utf-8") as f:
    f.write(content)

print("✓ Patch completed for all device types!")
