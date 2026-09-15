import json
import os
import socket
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path


class ExecutionLockError(RuntimeError):
    """Indica que o lock operacional nao pode ser adquirido ou liberado."""


class ExecutionLockService:
    """Controla um lock de arquivo atomico para uma unica automacao ativa."""

    def __init__(
        self,
        lock_path="runtime/collection.lock",
        stale_minutes=120,
        pid=None,
        hostname=None,
        username=None,
        command=None,
        now_function=None,
        process_checker=None,
    ):
        self.lock_path = Path(lock_path)
        self.stale_minutes = int(stale_minutes)
        if self.stale_minutes < 1:
            raise ValueError("stale_minutes deve ser maior que zero.")

        self.pid = int(os.getpid() if pid is None else pid)
        self.hostname = hostname or socket.gethostname()
        self.username = username or os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
        self.command = command or " ".join(sys.argv)
        self.now = now_function or (lambda: datetime.now(timezone.utc))
        self.process_checker = process_checker or self._default_process_checker
        self.acquired = False

    @staticmethod
    def _default_process_checker(pid):
        """Verifica se o processo informado ainda esta ativo."""

        process_id = int(pid)

        if process_id <= 0:
            return False

        if os.name == "nt":
            import ctypes
            from ctypes import wintypes

            process_query_limited_information = 0x1000
            still_active = 259

            kernel32 = ctypes.WinDLL(
                "kernel32",
                use_last_error=True,
            )

            kernel32.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            kernel32.OpenProcess.restype = wintypes.HANDLE

            kernel32.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL

            kernel32.CloseHandle.argtypes = [
                wintypes.HANDLE,
            ]
            kernel32.CloseHandle.restype = wintypes.BOOL

            handle = kernel32.OpenProcess(
                process_query_limited_information,
                False,
                process_id,
            )

            if not handle:
                return False

            try:
                exit_code = wintypes.DWORD()

                success = kernel32.GetExitCodeProcess(
                    handle,
                    ctypes.byref(exit_code),
                )

                return bool(
                    success
                    and exit_code.value == still_active
                )

            finally:
                kernel32.CloseHandle(handle)

        try:
            os.kill(process_id, 0)

        except ProcessLookupError:
            return False

        except PermissionError:
            return True

        except OSError:
            return False

        return True

    def _payload(self):
        return {
            "pid": self.pid,
            "hostname": self.hostname,
            "username": self.username,
            "started_at": self.now().isoformat(),
            "command": self.command,
        }

    def read_lock(self):
        if not self.lock_path.exists():
            return None
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ExecutionLockError(
                "O arquivo de lock existe, mas possui conteudo invalido."
            ) from error

        required = {"pid", "hostname", "username", "started_at", "command"}
        if not isinstance(data, dict) or not required.issubset(data):
            raise ExecutionLockError(
                "O arquivo de lock existe, mas esta incompleto."
            )
        return data

    def is_stale(self, data=None):
        lock = self.read_lock() if data is None else data
        if lock is None:
            return False

        try:
            started_at = datetime.fromisoformat(str(lock["started_at"]))
        except ValueError as error:
            raise ExecutionLockError("A data do arquivo de lock e invalida.") from error

        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        expired = self.now() - started_at > timedelta(minutes=self.stale_minutes)
        same_machine = str(lock["hostname"]).casefold() == str(self.hostname).casefold()
        process_dead = same_machine and not self.process_checker(int(lock["pid"]))
        return expired or process_dead

    def break_stale_lock(self):
        data = self.read_lock()
        if data is None:
            return False
        if not self.is_stale(data):
            raise ExecutionLockError(
                "O lock pertence a uma execucao que ainda pode estar ativa."
            )
        self.lock_path.unlink()
        return True

    def acquire(self, recover_stale=True):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        for _ in range(2):
            try:
                descriptor = os.open(
                    str(self.lock_path),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                )
            except FileExistsError:
                data = self.read_lock()
                if recover_stale and self.is_stale(data):
                    self.lock_path.unlink()
                    continue
                owner = "pid={pid}, maquina={hostname}, inicio={started_at}".format(**data)
                raise ExecutionLockError(
                    "Ja existe uma coleta em execucao: " + owner
                )

            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as file:
                    json.dump(self._payload(), file, ensure_ascii=False, indent=2)
                    file.flush()
                    os.fsync(file.fileno())
            except Exception:
                self.lock_path.unlink(missing_ok=True)
                raise

            self.acquired = True
            return self._payload()

        raise ExecutionLockError("Nao foi possivel adquirir o lock operacional.")

    def release(self):
        if not self.lock_path.exists():
            self.acquired = False
            return False

        data = self.read_lock()
        if int(data["pid"]) != self.pid or str(data["hostname"]).casefold() != str(self.hostname).casefold():
            raise ExecutionLockError(
                "O lock pertence a outro processo e nao pode ser liberado."
            )

        self.lock_path.unlink()
        self.acquired = False
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()
        return False
