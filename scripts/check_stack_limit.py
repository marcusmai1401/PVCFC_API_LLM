import logging
import sys
import threading


# Hàm đệ quy siêu nhẹ để test giới hạn số lượng lớp
def recursive_function(n, current_depth):
    if n <= 0:
        return "Done"
    if n % 1000000 == 0:  # In log mỗi 1 triệu lớp
        print(f"Running depth: {current_depth - n:,}...")
    return recursive_function(n - 1, current_depth)


def thread_target(limit):
    print(f"\n>>> TESTING RECURSION LIMIT: {limit:,} <<<")
    try:
        sys.setrecursionlimit(limit + 5000)
    except OverflowError:
        print("❌ Không thể set limit quá cao (Python giới hạn).")
        return False

    try:
        recursive_function(limit, limit)
        print(f"✅ PASSED: Máy chịu được {limit:,} lớp.")
        return True
    except RecursionError:
        print(f"⚠️ Python stopped it at {limit:,} (Safe RecursionError).")
        return True
    except MemoryError:
        print(f"❌ Crash: Hết RAM (MemoryError)!")
        return False
    except Exception as e:
        print(f"❌ Crash caused by other error: {e}")
        return False


def run_stress_test():
    # Test các mốc điên rồ: 2M, 5M, 10M
    levels = [2000000, 5000000, 10000000]

    print("--- STRESS TEST ROUND 4 (UNIVERSE MODE: 10 MILLION) ---")
    print("Đang xin OS cấp 512MB Stack Memory...")
    print("-" * 50)

    # Xin cấp 512MB Stack. Nếu máy không đủ RAM liền mạch, lệnh này sẽ lỗi.
    try:
        threading.stack_size(512 * 1024 * 1024)
    except Exception as e:
        print(f"❌ Không thể xin cấp 512MB Stack: {e}")
        print("Thử giảm xuống 128MB...")
        try:
            threading.stack_size(128 * 1024 * 1024)
        except:
            print("❌ Vẫn thất bại. Chạy với stack mặc định (sẽ fail ở mức cao).")

    for level in levels:
        t = threading.Thread(target=thread_target, args=(level,))
        t.start()
        t.join()

        if not t.is_alive():
            print(f"Finished test level {level:,}.")
        else:
            print(f"❌ Thread died silently (Stack Overflow) at level {level:,}.")
            break


if __name__ == "__main__":
    run_stress_test()
