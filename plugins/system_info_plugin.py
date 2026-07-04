NAME = "System Info Plugin"

def can_handle(command: str) -> bool:
    c = command.lower()
    return "system info" in c or "pc info" in c or "hardware info" in c

def handle(command: str, context: dict) -> str:
    import platform
    import os
    return (
        f"System: {platform.system()} {platform.release()}\n"
        f"CPU: {platform.processor()}\n"
        f"Python: {platform.python_version()}\n"
        f"User: {os.getenv('USERNAME','')}"
    )
