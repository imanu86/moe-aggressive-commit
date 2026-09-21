"""Spegne llama-server in modo GRAZIOSO: gli manda CTRL_C sulla sua console, come se lo premessi tu.

llama-server ha un gestore di CTRL_C che chiude il contesto CUDA e rilascia la memoria bloccata;
`taskkill /F` e `Stop-Process -Force` no (regola del 27/7 e del 12/8). Lo script si attacca alla console del
server, manda CTRL_C, aspetta fino a 120 s l'uscita spontanea e poi chiude il cmd.exe del lanciatore rimasto
appeso sulla domanda «Terminare il processo batch?». Non forza mai l'uscita del server: se non esce lo dice.
"""
from __future__ import annotations
import ctypes
import subprocess
import sys
import time

K = ctypes.windll.kernel32


def processi() -> list[tuple[int, int]]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-CimInstance Win32_Process -Filter \"Name='llama-server.exe'\" | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }"],
                         capture_output=True, text=True).stdout.split()
    return [(int(out[i]), int(out[i + 1])) for i in range(0, len(out) - 1, 2)]


def vivo(pid: int) -> bool:
    return any(p == pid for p, _ in processi())


def main() -> int:
    trovati = processi()
    if not trovati:
        print("nessun llama-server acceso")
        return 0
    for pid, padre in trovati:
        K.FreeConsole()
        if not K.AttachConsole(pid):
            print(f"PID {pid}: non riesco ad attaccarmi alla sua console (errore {K.GetLastError()}): non lo tocco")
            continue
        K.SetConsoleCtrlHandler(None, True)  # il CTRL_C non deve uccidere questo script
        K.GenerateConsoleCtrlEvent(0, 0)
        time.sleep(1)
        K.FreeConsole()
        K.SetConsoleCtrlHandler(None, False)
        t0 = time.time()
        while vivo(pid) and time.time() - t0 < 120:
            time.sleep(2)
        if vivo(pid):
            print(f"PID {pid}: dopo 120 s e' ancora vivo. NON lo forzo: guarda la sua finestra o il log.")
            return 1
        print(f"PID {pid}: uscito da solo in {time.time() - t0:.0f} s")
        nome = subprocess.run(["tasklist", "/FI", f"PID eq {padre}", "/NH", "/FO", "CSV"], capture_output=True, text=True).stdout
        if nome.lower().startswith('"cmd.exe"'):  # solo il cmd.exe del lanciatore, mai un runner python
            subprocess.run(["taskkill", "/PID", str(padre), "/T", "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
