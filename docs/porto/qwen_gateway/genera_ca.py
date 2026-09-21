"""Genera la CA locale e il certificato di api.anthropic.com per il gateway.

Sicurezza:
  - la CA e' vincolata (nameConstraints, critico) al solo nome api.anthropic.com;
  - la chiave privata della CA viene CANCELLATA subito dopo la firma: non si possono emettere altri
    certificati; alla scadenza si rigenera tutto;
  - i file stanno in %USERPROFILE%\\.claude\\qwen-gateway, con ACL ristrette all'utente, FUORI dal repo;
  - la CA non va MAI installata nello store di Windows: la legge solo Claude Code, tramite
    NODE_EXTRA_CA_CERTS.
"""
from __future__ import annotations
import getpass
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEST = Path(os.environ["USERPROFILE"]) / ".claude" / "qwen-gateway"
HOST = "api.anthropic.com"


def openssl() -> str:
    for c in (shutil.which("openssl"), r"C:\Program Files\Git\mingw64\bin\openssl.exe",
              r"C:\Program Files\Git\usr\bin\openssl.exe"):
        if c and Path(c).exists():
            return c
    sys.exit("openssl non trovato")


def main() -> int:
    if (DEST / "leaf.pem").exists():
        sys.exit(f"certificati gia' presenti in {DEST}: non sovrascrivo (cancella la cartella per rigenerare)")
    DEST.mkdir(parents=True, exist_ok=True)
    subprocess.run(["icacls", str(DEST), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:(OI)(CI)F"],
                   check=True, capture_output=True)
    ssl = openssl()

    def run(*a: str) -> None:
        r = subprocess.run([ssl, *a], cwd=DEST, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"openssl {' '.join(a[:2])} fallito:\n{r.stderr}")

    run("req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", "ca.key", "-out", "ca.pem", "-days", "830", "-subj", "/CN=Qwen Gateway CA locale - solo Claude Code",
        "-addext", "basicConstraints=critical,CA:TRUE,pathlen:0", "-addext", "keyUsage=critical,keyCertSign",
        "-addext", f"nameConstraints=critical,permitted;DNS:{HOST}")
    run("req", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes",
        "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", f"/CN={HOST}")
    (DEST / "leaf.ext").write_text(f"subjectAltName=DNS:{HOST}\nextendedKeyUsage=serverAuth\n"
                                   "basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n",
                                   encoding="ascii")
    run("x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
        "-out", "leaf.pem", "-days", "825", "-extfile", "leaf.ext")
    for nome in ("ca.key", "ca.srl", "leaf.csr", "leaf.ext"):
        (DEST / nome).unlink(missing_ok=True)
    assert not (DEST / "ca.key").exists()
    print("fatto:", DEST)
    print("  ca.pem   -> NODE_EXTRA_CA_CERTS (pubblico)")
    print("  leaf.pem + leaf.key -> il gateway (la chiave della CA e' stata cancellata)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
