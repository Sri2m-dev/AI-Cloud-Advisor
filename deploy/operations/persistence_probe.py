"""Synthetic-only named-volume container replacement probe; never real data."""
import json
from pathlib import Path
import sys
from cryptography.fernet import Fernet


def main(mode, root):
    root = Path(root)
    key_file, data_file = root / "synthetic-probe.key", root / "synthetic-probe.enc"
    if mode == "write":
        # This probe volume is isolated from every application/evidence volume.
        key = Fernet.generate_key()
        with key_file.open("xb") as output: output.write(key)
        with data_file.open("xb") as output: output.write(Fernet(key).encrypt(b"nexora synthetic replacement probe"))
    elif mode == "verify":
        if Fernet(key_file.read_bytes()).decrypt(data_file.read_bytes()) != b"nexora synthetic replacement probe":
            raise ValueError("replacement persistence failed")
    else: raise ValueError("unknown probe mode")
    print(json.dumps({"synthetic_probe": mode, "status": "COMPLETE"}))


if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
