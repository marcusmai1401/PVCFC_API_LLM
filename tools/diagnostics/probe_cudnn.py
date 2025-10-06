import ctypes
import importlib.util
import os
import sys

# add paths
added = []
for pkg in ["nvidia.cuda_runtime", "nvidia.cudnn", "nvidia.cublas"]:
    spec = importlib.util.find_spec(pkg)
    if spec and spec.submodule_search_locations:
        d = spec.submodule_search_locations[0]
        bin_d = os.path.join(d, "bin")
        if os.path.isdir(bin_d):
            os.add_dll_directory(bin_d)
            added.append(bin_d)
print("Added:", added)

try:
    cdll = ctypes.CDLL("cudnn64_8.dll")
    print("Loaded cudnn64_8.dll OK:", cdll)
except OSError as e:
    print("Failed to load cudnn64_8.dll:", e)
    sys.exit(1)
