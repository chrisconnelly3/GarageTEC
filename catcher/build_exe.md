# Building GolfShotCatcher.exe

PyInstaller is a build-time tool only (not a runtime/dev dependency).

## One-time
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install pyinstaller
```

## Build (from repo root)
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller ^
  --onefile --windowed --name GolfShotCatcher ^
  --collect-submodules store --collect-data store ^
  catcher/run.py
```
Output: `dist\GolfShotCatcher.exe`.

`--collect-data store` bundles `store/schema.sql` so `init_db` works inside the
frozen exe.

## Verify
```
dist\GolfShotCatcher.exe --selftest      # prints "selftest ok", exits 0
```

## Runtime data location
The exe writes `garagetec.db` + `pending_shots.jsonl` under the store's default
`data/` directory. Override with `--db <path>` or the `GARAGETEC_DATA_DIR`
environment variable.

## Windows Firewall
On first run Windows may prompt to allow the app on the network (it listens on
TCP 921). Click **Allow**.
