from app.utils.ui_logger import get_logger

payload = {
    "api_key": "sk-123456",
    "password": "P@ssw0rd!",
    "secret": "supersecret",
    "nested": {"token": "abcDEF123"},
    "headers": {"Authorization": "Bearer abc.def"},
}
logger = get_logger(reinitialize=True, enable_console_logging=False)
print("Input:", payload)
print("Redacted:", logger._redact_sensitive_data(payload))
