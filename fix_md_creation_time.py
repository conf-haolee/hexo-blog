import os
import sys
import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime

# -------- Windows FILETIME helpers --------
EPOCH_AS_FILETIME = 116444736000000000  # 1970-01-01 as FILETIME (100-ns since 1601)
HUNDREDS_OF_NS = 10_000_000

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CreateFileW = kernel32.CreateFileW
CreateFileW.argtypes = [
    wintypes.LPCWSTR,  # lpFileName
    wintypes.DWORD,    # dwDesiredAccess
    wintypes.DWORD,    # dwShareMode
    wintypes.LPVOID,   # lpSecurityAttributes
    wintypes.DWORD,    # dwCreationDisposition
    wintypes.DWORD,    # dwFlagsAndAttributes
    wintypes.HANDLE    # hTemplateFile
]
CreateFileW.restype = wintypes.HANDLE

SetFileTime = kernel32.SetFileTime
SetFileTime.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.FILETIME),  # CreationTime
    ctypes.POINTER(wintypes.FILETIME),  # LastAccessTime
    ctypes.POINTER(wintypes.FILETIME),  # LastWriteTime
]
SetFileTime.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080

def _raise_last_error(prefix: str):
    err = ctypes.get_last_error()
    raise OSError(f"{prefix} (WinError={err})")

def unix_ts_to_filetime(ts: float) -> wintypes.FILETIME:
    # ts is seconds since 1970-01-01 (UTC-ish; filesystem stores as UTC internally)
    ft = int(ts * HUNDREDS_OF_NS) + EPOCH_AS_FILETIME
    low = ft & 0xFFFFFFFF
    high = (ft >> 32) & 0xFFFFFFFF
    return wintypes.FILETIME(low, high)

def set_creation_time_to_mtime(path: str, also_set_last_write: bool = True, dry_run: bool = False):
    st = os.stat(path)
    mtime = st.st_mtime

    if dry_run:
        print(f"[DRY] {path}")
        print(f"      mtime = {datetime.fromtimestamp(mtime)}")
        return

    handle = CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    if handle == INVALID_HANDLE_VALUE:
        _raise_last_error(f"CreateFileW failed: {path}")

    try:
        ft_m = unix_ts_to_filetime(mtime)
        p_creation = ctypes.byref(ft_m)
        p_access = None  # 不改访问时间
        p_write = ctypes.byref(ft_m) if also_set_last_write else None

        ok = SetFileTime(handle, p_creation, p_access, p_write)
        if not ok:
            _raise_last_error(f"SetFileTime failed: {path}")
    finally:
        CloseHandle(handle)

def walk_md_files(root: str, excludes: set[str]):
    for dirpath, dirnames, filenames in os.walk(root):
        # 目录过滤（原地修改 dirnames 才能阻止递归进入）
        dirnames[:] = [d for d in dirnames if d not in excludes]
        for fn in filenames:
            if fn.lower().endswith(".md"):
                yield os.path.join(dirpath, fn)

def main():
    if os.name != "nt":
        print("这个脚本只用于 Windows（因为要改 CreationTime）。")
        sys.exit(1)

    ap = argparse.ArgumentParser(description="Set .md CreationTime to its mtime (Windows/NTFS).")
    ap.add_argument("root", nargs="?", default=".", help="项目根目录（默认当前目录）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不修改")
    ap.add_argument("--only-posts", action="store_true", help="只处理 Hexo 的 source/_posts 下的 .md")
    ap.add_argument("--excludes", default=".git,node_modules,public,.deploy_git,.idea,.vscode",
                    help="排除目录（逗号分隔）")
    ap.add_argument("--dont-touch-write", action="store_true",
                    help="只改 CreationTime，不改 LastWriteTime")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    excludes = set([x.strip() for x in args.excludes.split(",") if x.strip()])

    if args.only_posts:
        target_root = os.path.join(root, "source", "_posts")
        if not os.path.isdir(target_root):
            print(f"找不到目录：{target_root}")
            sys.exit(2)
    else:
        target_root = root

    count = 0
    for p in walk_md_files(target_root, excludes):
        set_creation_time_to_mtime(
            p,
            also_set_last_write=not args.dont_touch_write,
            dry_run=args.dry_run
        )
        count += 1

    print(f"Done. processed {count} files under: {target_root}")

if __name__ == "__main__":
    main()
