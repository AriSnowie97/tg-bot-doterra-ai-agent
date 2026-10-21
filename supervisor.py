"""doTERRA Bot — Легковагий супервізор процесів для Railway / Docker.

1. Запускає початкову синхронізацію контенту (sync_content.py).
2. Запускає веб-сервер FastAPI та ботів як дочірні процеси.
3. Моніторить стан процесів: якщо процес аварійно завершився — перезапускає його
   з затримкою (cooldown).
4. Коректно пересилає SIGTERM / SIGINT для graceful shutdown.
"""

# Standard
import os
import signal
import subprocess
import sys
import time

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src.safety import redact

MAX_CRASHES = int(os.getenv("SUPERVISOR_MAX_CRASHES", "5"))
CRASH_WINDOW = int(os.getenv("SUPERVISOR_CRASH_WINDOW", "60"))

# Опис сервісів
SERVICES_DEF = [
    {
        "name": "web_api",
        "cmd": [
            sys.executable,
            "-m",
            "uvicorn",
            "src.web.app:app",
            "--host",
            "0.0.0.0",
            "--port",
            os.getenv("PORT", "8000"),
        ],
        "enabled": lambda: True,
        "critical": True,
    },
    {
        "name": "main_bot",
        "cmd": [sys.executable, "bot.py"],
        "enabled": lambda: bool(os.getenv("BOT_TOKEN")),
        "critical": True,
    },
    {
        "name": "kb_bot",
        "cmd": [sys.executable, "kb_bot.py"],
        "enabled": lambda: bool(os.getenv("KB_BOT_TOKEN") and os.getenv("KB_ADMIN_IDS")),
        "critical": False,
    },
    {
        "name": "uploader_bot",
        "cmd": [sys.executable, "content_uploader_bot.py"],
        "enabled": lambda: bool(os.getenv("CONTENT_BOT_TOKEN") and os.getenv("CONTENT_BOT_ADMINS")),
        "critical": False,
    },
]


def start_initial_sync() -> subprocess.Popen | None:
    """Запускає початкову синхронізацію контенту у фоновому процесі.

    Не блокує запуск FastAPI та ботів, щоб Railway міг одразу перевірити порт $PORT
    і боти були доступні для користувачів без затримки.
    """
    print("[supervisor] 🔄 Launching initial content sync in background (sync_content.py)...", flush=True)
    try:
        p = subprocess.Popen([sys.executable, "src/content/sync_content.py"])
        return p
    except Exception as e:
        print(f"[supervisor] ⚠️ Failed to launch initial sync: {redact(e)}", flush=True)
        return None


def main() -> None:
    print("[supervisor] 🚀 Starting supervisor...", flush=True)
    sync_proc: subprocess.Popen | None = start_initial_sync()

    processes: dict[str, subprocess.Popen] = {}
    restart_history: dict[str, list[float]] = {}
    running = True

    def _shutdown(exit_code: int = 0) -> None:
        nonlocal running
        print(f"\n[supervisor] Stopping all services (exit_code={exit_code})...", flush=True)
        running = False

        if sync_proc and sync_proc.poll() is None:
            sync_proc.terminate()
        for name, p in processes.items():
            if p.poll() is None:
                p.terminate()

        time.sleep(2)

        if sync_proc and sync_proc.poll() is None:
            sync_proc.kill()
        for name, p in processes.items():
            if p.poll() is None:
                p.kill()

        sys.exit(exit_code)

    def _sig_handler(signum, frame):
        print(f"\n[supervisor] Received signal {signum}, initiating graceful shutdown...", flush=True)
        _shutdown(exit_code=0)

    try:
        signal.signal(signal.SIGTERM, _sig_handler)
        signal.signal(signal.SIGINT, _sig_handler)
    except Exception:
        pass  # Windows threading/signal nuances

    def _start_service(s: dict) -> None:
        name = s["name"]
        print(f"[supervisor] 🟢 Starting service '{name}': {' '.join(s['cmd'])}", flush=True)
        processes[name] = subprocess.Popen(s["cmd"])

    # Запускаємо всі активні сервіси
    for s in SERVICES_DEF:
        if s["enabled"]():
            _start_service(s)
            restart_history[s["name"]] = []
        else:
            print(f"[supervisor] ⚪ Service '{s['name']}' disabled (missing env vars)", flush=True)

    print("[supervisor] 👀 All active services started. Entering monitor loop.", flush=True)

    while running:
        time.sleep(3)
        now = time.monotonic()

        # Перевірка фонового процесу синхронізації
        if sync_proc is not None:
            ret_sync = sync_proc.poll()
            if ret_sync is not None:
                print(f"[supervisor] ℹ️ Background initial sync finished with exit code {ret_sync}", flush=True)
                sync_proc = None

        for s in SERVICES_DEF:
            name = s["name"]
            if name not in processes:
                continue

            proc = processes[name]
            ret = proc.poll()
            if ret is not None:
                print(f"[supervisor] ⚠️ Service '{name}' exited with code {ret}!", flush=True)

                # Перевіряємо історію падінь
                history = restart_history[name]
                history = [t for t in history if now - t < CRASH_WINDOW]
                history.append(now)
                restart_history[name] = history

                if len(history) >= MAX_CRASHES:
                    is_critical = s.get("critical", False)
                    if not is_critical:
                        # Допоміжний бот впав забагато разів — просто вимикаємо його,
                        # не зупиняючи основний бот та веб-сервер
                        print(
                            f"[supervisor] 🛑 Non-critical service '{name}' crashed {len(history)} times "
                            f"in {CRASH_WINDOW}s. Disabling this service to keep core system running.",
                            flush=True,
                        )
                        del processes[name]
                        continue
                    else:
                        # Критичний сервіс (web_api або main_bot) впав забагато разів —
                        # завершуємо роботу супервізора з КОДОМ 1, щоб Railway (ON_FAILURE)
                        # перезапустив весь контейнер!
                        print(
                            f"[supervisor] ❌ Critical service '{name}' crashed {len(history)} times "
                            f"in {CRASH_WINDOW}s. Exiting supervisor with code 1 to trigger platform restart.",
                            flush=True,
                        )
                        _shutdown(exit_code=1)
                        return

                # Перезапускаємо сервіс
                print(f"[supervisor] 🔄 Restarting service '{name}' in 3 seconds...", flush=True)
                time.sleep(3)
                if running:
                    _start_service(s)


if __name__ == "__main__":
    main()

