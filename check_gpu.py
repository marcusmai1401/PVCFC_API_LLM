#!/usr/bin/env python
import paddle

print(f"PaddlePaddle: {paddle.__version__}")
print(f"CUDA compiled: {paddle.is_compiled_with_cuda()}")

if paddle.is_compiled_with_cuda():
    print(f"CUDA version: {paddle.version.cuda()}")
    print(f"cuDNN version: {paddle.version.cudnn()}")

    try:
        # Test GPU initialization
        paddle.set_device("gpu:0")
        x = paddle.randn([2, 3])
        print(f"✅ GPU test successful: {x.place}")
    except Exception as e:
        print(f"❌ GPU test failed: {e}")
else:
    print("❌ CUDA not compiled")
