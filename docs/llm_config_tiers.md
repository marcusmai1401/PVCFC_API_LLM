# LLM tiers and embedding configuration

## Mục tiêu
- Cho phép dùng “LLM tầng nhẹ” (rẻ/nhanh) cho dev/QA và “LLM tầng nặng” (chất lượng cao) cho trả lời cuối.
- Hỗ trợ dùng provider khác nhau cho từng vai trò: heavy/light (generator) và embedding.
- Chuyển đổi bằng cách sửa `.env` (không cần đổi code).

## Biến môi trường (xem mẫu trong `env.example`)
- Generator (heavy/light):
  - `LLM_PROVIDER`: provider chính (heavy) — openai|gemini|none
  - `LLM_TIER`: light|heavy (tuỳ chọn sử dụng khi gọi)
  - `LLM_LIGHT_PROVIDER`: provider cho tier nhẹ (tuỳ chọn). Nếu trống → fallback `LLM_PROVIDER`.
  - `LLM_MODEL_LIGHT`, `LLM_MODEL_HEAVY`: tên model theo tier.
- API keys theo provider bạn sử dụng thực tế:
  - `OPENAI_API_KEY`, `GEMINI_API_KEY`
- Embedding:
  - `EMBEDDING_PROVIDER`: openai|local|none
  - `EMBEDDING_LLM`: alias cho provider embedding (tuỳ chọn), mục đích giúp đọc config dễ hơn.
  - `EMBEDDING_MODEL`: tên model embedding.

Ví dụ `.env`:
```env
# Heavy (Gemini 2.5 Pro - high quality)
LLM_PROVIDER=gemini
LLM_MODEL_HEAVY=gemini-2.5-pro
GEMINI_API_KEY=...

# Light (Gemini 2.5 Flash - newest and fastest)
LLM_MODEL_LIGHT=gemini-2.5-flash
# Hoặc dùng OpenAI nếu muốn:
# LLM_LIGHT_PROVIDER=openai
# LLM_MODEL_LIGHT=gpt-4o-mini
# OPENAI_API_KEY=...

# Embedding (OpenAI)
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
```

## Cấu hình và helpers trong code
- `app/core/config.py`:
  - Thêm fields: `llm_tier`, `llm_light_provider`, `llm_model_light`, `llm_model_heavy`.
  - Thêm fields: `embedding_provider`, `embedding_llm`, `embedding_model`.
  - Helpers:
    - `provider_for_tier(tier)`: trả về provider ứng với tier (light → `llm_light_provider` hoặc fallback `llm_provider`; heavy → `llm_provider`).
    - `embedding_provider_effective()`: trả về provider embedding hiệu lực (ưu tiên `embedding_llm`, fallback `embedding_provider`).
- `app/services/llm.py`:
  - `get_provider_for(tier)`, `get_model_for(tier)`, `get_api_key_for(provider)`.
  - `get_embedding_provider()`, `get_embedding_model()`.

Cách dùng (ví dụ):
```python
from app.services.llm import (
    get_provider_for, get_model_for, get_api_key_for,
    get_embedding_provider, get_embedding_model,
)

provider = get_provider_for("light")
model = get_model_for("light")
api_key = get_api_key_for(provider)
```

## Tương thích & kiểm thử
- Health endpoint/tests không đổi (chỉ kiểm `llm_provider` và `llm_provider_ready`).
- Việc log/mask không bị ảnh hưởng; không log API keys trong response.

## Lý do thiết kế
- Đơn giản hoá việc thử nghiệm với chi phí thấp và chuyển sang chất lượng cao khi cần.
- Linh hoạt kết hợp nhà cung cấp: ví dụ heavy = Gemini, light + embedding = OpenAI.
- Hạn chế ràng buộc vào một provider cụ thể; model name đặt trong `.env` để đổi nhanh.
