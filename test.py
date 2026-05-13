#!/usr/bin/env python3
import os
import subprocess
import threading
import time
import tempfile
import shutil
import signal
import sys

# -------- CONFIG --------
FUSE_BINARY = "fsx492"          # your compiled FS
FUSE_ARGS = ["-f", "-d", "-s"]  # run single threaded debug mode
MOUNT_TIMEOUT = 10              # seconds
# ------------------------


##############################################################################
# BEGIN TEST DEFINITIONS
##############################################################################

# define tests below by creating functions that are prefixed with "test_"


def test_basic(mountpoint):

    # TEST: directory listing

    print(f"[test] list {mountpoint}")
    entries = os.listdir(mountpoint)
    print(entries)
    assert "hello.txt" in entries, "readdir missing file"

    # TEST: file existence
    path = os.path.join(mountpoint, "hello.txt")
    print(f"[test] file existence: {path}")
    assert os.path.exists(path), "file missing"

    # TEST: read
    print(f"[test] read {path}")
    with open(path, "r") as f:
        data = f.read()
    assert "hello" in data, "unexpected file content"

    # TEST: partial read
    print(f"[test] partial read {path}")
    with open(path, "r") as f:
        f.seek(6)
        data = f.read()
    assert "world" in data, "partial read failed"

    # TEST: out of bounds read
    print(f"[test] out of bounds read {path}")
    with open(path, "r") as f:
        f.seek(30)
        data = f.read()
    assert len(data) == 0, "out of bounds read should return nothing"

    # TEST: stat
    print(f"[test] stat {path}")
    st = os.stat(path)
    assert st.st_size == len("hello world!\n"), "invalid file size"

    print("[test] passed basic")


def test_large_file(mountpoint):

    # TEST: large file copy
    src = "./data/gospels.txt"
    assert os.path.exists(src), "src not found: {}".format(src)

    dst = f"{mountpoint}/{os.path.basename(src)}"
    shutil.copy(src, dst)
    assert os.path.exists(dst), "copy failed: {} does not exist".format(dst)

    with open(src, 'rb') as f:
        srcdata = f.read()

    with open(dst, 'rb') as f:
        dstdata = f.read()

    assert len(srcdata) == len(dstdata), \
        "length check failed: {} (src) != {} (dst)".format(
            len(srcdata), len(dstdata))

    diff = -1
    for i in range(len(srcdata)):
        if srcdata[i] != dstdata[i]:
            diff = i
            break

    assert diff < 0, "data different @ {}:\nsrc: {}\ndst: {}".format(
        diff, srcdata[diff:diff+10], dstdata[diff:diff+10])

    print("[test] passed large file")

def test_subdir_file_creation_deletion(mountpoint):
    # adding and removing files from subdirectories

    # create subdir
    subdir = os.path.join(mountpoint, "subdir") # `.../subdir`
    os.mkdir(subdir)
    print("[test] created subdirectory: " + str(subdir))

    # add multiple files to subdir
    created_files = ['agore1.txt', 'supadhya.md', 'jchoi14.c']
    for file_name in created_files:
        file_path = os.path.join(subdir, file_name)
        with open(file_path, "w") as file_open:
            file_content = "this is a file named: " + file_name
            file_open.write(file_content)
        print("[test] added file " + str(file_path))

    # check if all files appear in subdir
    listed_files = os.listdir(subdir)
    check = 0
    for file_name in created_files:
        if (file_name not in listed_files):
            check += 1
    
    if (check > 0):
        print("[test] file adding unsuccessful, missing " + str(check) + " files")
        assert_text = "missing " + str(check) + " files in subdir"
        assert False, assert_text
    else:
        print("[test] file adding successful")


    # remove files from subdir
    for file_name in created_files:
        file_path = os.path.join(subdir, file_name)
        os.remove(file_path)
        print("[test] removed file " + str(file_path))
        if os.path.exists(file_path):
            assert_text = "file still exists: " + file_path
            assert False, assert_text
    
    # check if subdir is empty
    listed_files = os.listdir(subdir)
    if (len(listed_files) > 0):
        assert False, "subdir not empty"


    # delete subdir
    os.rmdir(subdir)
    if os.path.exists(subdir):
        assert False, "failed to delete subdir"

    print("[test] passed adding and removing files from subdirectories")

def test_creating_multiple_dirs(mountpoint):
    # adding and removing more than a block's worth of directories (at once)

    # one dir block holds 32 entries, so 50 should span at least 2 blocks
    entries = 50

    # create base dir to hold all the subdirs
    base = os.path.join(mountpoint, "manydirs")
    os.mkdir(base)
    print("[test] created base directory: " + str(base))

    # create dirs
    created_dirs = []
    for i in range(entries):
        created_dirs += ["directory" + str(i)]

    for dir_name in created_dirs:
        dir_path = os.path.join(base, dir_name)
        os.mkdir(dir_path)
        # print("[test] created directory " + str(dir_path))
    print("[test] added " + str(entries) + " subdirectories")

    # check if all dirs appear in base
    listed_dirs = os.listdir(base)
    check = 0
    for dir_name in created_dirs:
        if (dir_name not in listed_dirs):
            check += 1

    if (check > 0):
        print("[test] directory creation unsuccessful, missing " + str(check) + " directories")
        assert_text = "missing " + str(check) + " directories in subdir"
        assert False, assert_text
    else:
        print("[test] directory creation successful")

    # remove all dirs
    for dir_name in created_dirs:
        dir_path = os.path.join(base, dir_name)
        # print("[test] removed directory " + str(dir_path))
        os.rmdir(dir_path)
        if os.path.exists(dir_path):
            assert False, "dir still exists: " + dir_path
    print("[test] removed all " + str(entries) + " subdirectories")

    # check if base is empty
    listed_dirs = os.listdir(base)
    if (len(listed_dirs) > 0):
        assert False, "base not empty"


    # delete base
    os.rmdir(base)
    if os.path.exists(base):
        assert False, "failed to delete base"

    print("[test] passed adding and removing more than a block of directories")

def test_overwriting_files(mountpoint):
    # overwriting a file

    file_path = os.path.join(mountpoint, "file1.txt")

    # initialize file with content
    primary = "abc abc abc abc abc abc abc"
    with open(file_path, "w") as file_open:
        file_open.write(primary)
    print("[test] wrote primary file content (" + str(len(primary)) + " bytes)")

    status = os.stat(file_path)
    if status.st_size != len(primary):
        assert_text = "wrong primary file size: expected " + str(len(primary)) + ", got " + str(status.st_size)
        assert False, assert_text

    # overwrite with shorter content
    shorter = "def"
    with open(file_path, "w") as file_open:
        file_open.write(shorter)
    print("[test] overwrote file with shorter content (" + str(len(shorter)) + " bytes)")

    # check size shrunk correctly
    status = os.stat(file_path)
    if status.st_size != len(shorter):
        assert False, "wrong size after shorter overwrite: expected " + str(len(shorter)) + ", got " + str(status.st_size)

    # check contents are fully replaced (no leftover bytes)
    with open(file_path, "r") as file_open:
        data = file_open.read()
    if data != shorter:
        assert False, "wrong content after shorter overwrite: expected " + repr(shorter) + ", got " + repr(data)
    print("[test] shorter overwrite successful")

    # overwrite with longer content
    longer = "ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi"
    with open(file_path, "w") as file_open:
        file_open.write(longer)
    print("[test] overwrote with longer content (" + str(len(longer)) + " bytes)")

    # check size grew
    status = os.stat(file_path)
    if status.st_size != len(longer):
        assert False, "wrong size after longer overwrite: expected " + str(len(longer)) + ", got " + str(status.st_size)

    # check contents
    with open(file_path, "r") as file_open:
        data = file_open.read()
    if data != longer:
        assert False, "wrong content after longer overwrite: expected " + repr(longer) + ", got " + repr(data)
    print("[test] longer overwrite successful")

    # clean up
    os.remove(file_path)
    if os.path.exists(file_path):
        assert False, "failed to delete file"

    print("[test] passed file overwrite")

def test_open_file_append_mode(mountpoint):
    # opening a file in "append" mode

    file_path = os.path.join(mountpoint, "appendfile.txt")

    # initialize file with some content
    initial = "abcdef\n"
    with open(file_path, "w") as file_open:
        file_open.write(initial)
    print("[test] wrote initial content (" + str(len(initial)) + " bytes)")

    status = os.stat(file_path)
    if status.st_size != len(initial):
        assert False, "wrong initial size: expected " + str(len(initial)) + ", got " + str(status.st_size)

    # append second chunk of data
    second = "ghijkl\n"
    with open(file_path, "a") as file_open: # append mode
        file_open.write(second)
    print("[test] appended (" + str(len(second)) + " bytes)")

    # check size grew by exactly len(second), existing content preserved
    status = os.stat(file_path)
    expected_size = len(initial) + len(second)
    if status.st_size != expected_size:
        assert False, "wrong size after append: expected " + str(expected_size) + ", got " + str(status.st_size)

    # append third chunk
    third = "mnopqr\n"
    with open(file_path, "a") as file_open:# append mode
        file_open.write(third)
    print("[test] appended (" + str(len(third)) + " bytes)")

    status = os.stat(file_path)
    expected_size = len(initial) + len(second) + len(third)
    if status.st_size != expected_size:
        assert False, "wrong size after second append: expected " + str(expected_size) + ", got " + str(status.st_size)

    # check final contents are everything in order
    with open(file_path, "r") as file_open:
        data = file_open.read()
    expected_data = initial + second + third
    if data != expected_data:
        assert False, "wrong content after appends: expected " + repr(expected_data) + ", got " + repr(data)
    print("[test] appends in correct order")

    # opening in "append" mode and closing should leave file unchanged
    with open(file_path, "a") as file_open: # append mode
        pass
    status = os.stat(file_path)
    if status.st_size != expected_size:
        assert False, "append-open changed size: expected " + str(expected_size) + ", got " + str(status.st_size)
    print("[test] append-open did not modify file")

    # clean up
    os.remove(file_path)
    if os.path.exists(file_path):
        assert False, "failed to delete file"

    print("[test] passed append mode")

##############################################################################
# END TEST DEFINITIONS
##############################################################################

TESTS = {
    k.lstrip('test_'): v for k, v in globals().items() if k.startswith('test_')
}


def reset_mount(mountpoint, fs_name=FUSE_BINARY):
    """reset fuse filesystem mountpoint after failure"""
    result = subprocess.run(
        ['mount'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False)

    if fs_name in result.stdout:
        subprocess.run(
            ['fusermount', '-u', mountpoint],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False)

    try:
        shutil.rmtree(mountpoint)
    except Exception:
        pass

    os.makedirs(mountpoint, exist_ok=True)

def is_mounted(mountpoint, fs_name=None):
    mountpoint = os.path.abspath(mountpoint)

    try:
        with open("/proc/self/mounts", "r") as f:
            lines = [line.strip() for line in f.readlines()]

        for line in lines:
            parts = line.split()
            if len(parts) < 3:
                continue

            dev, mnt, fstype = parts[:3]

            if os.path.abspath(mnt) == mountpoint:
                if fs_name is None:
                    return True
                if fs_name in dev or fs_name in fstype:
                    return True
        return False
    except Exception:
        return False


def wait_for_mount(mountpoint, timeout=MOUNT_TIMEOUT):
    """Wait until mountpoint is ready by probing it."""
    start = time.time()
    while time.time() - start < timeout:
        if is_mounted(mountpoint, fs_name="fsx492"):
            return True
        time.sleep(0.1)
    return False


def run_filesystem(mountpoint, ready_event, stop_event, logfile="fsx492.log"):
    """Run the FUSE filesystem."""
    cmd = ['stdbuf', '-oL', '-eL'] + [f"./{FUSE_BINARY}"] + FUSE_ARGS + [mountpoint]

    # unmount file system if needed first
    reset_mount(mountpoint)

    log = open(logfile, 'w')
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Wait until mount is ready
    if wait_for_mount(mountpoint):
        print("[fs] mounted")
        ready_event.set()
    else:
        print("[fs] mount timeout")
        proc.terminate()
        return

    # Keep process alive until stop_event
    while not stop_event.is_set():
        if proc.poll() is not None:
            print("[fs] process exited early!")
            return
        time.sleep(0.2)

    log.close()
    print("[fs] shutting down...")
    proc.send_signal(signal.SIGINT)

    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_tests(test, mountpoint, ready_event, stop_event):
    """Run filesystem tests."""
    ready_event.wait()

    print(f"[test] starting test: {test}")

    try:
        TESTS[test](mountpoint)
    except AssertionError as e:
        print(f"[test] FAILED: {e}")
    finally:
        stop_event.set()


if __name__ == "__main__":
    DEFAULT_MOUNTPOINT = './testfs'
    DEFAULT_IMAGE = 'data/test.img'
    import argparse
    parser = argparse.ArgumentParser('test.py',
        description="test script for fsx492")
    parser.add_argument('test', type=str, default='basic',
        help=f"options: {','.join(TESTS.keys())}")
    parser.add_argument('--mountpoint', type=str, default=DEFAULT_MOUNTPOINT,
        help=f"the path to mount at (default {DEFAULT_MOUNTPOINT})")
    parser.add_argument('--img', type=str, default='data/test.img',
        help=("the path to the image file, which will be restored from backup "
            f"(default: {DEFAULT_IMAGE})"))

    args = parser.parse_args()

    mountpoint = args.mountpoint
    assert args.test in TESTS, "test not found: {}".format(args.test)
    assert callable(TESTS[args.test]), "not callable: {}".format(args.test)

    imgpath = args.img
    assert os.path.exists(imgpath), "file not found: {}".format(imgpath)
    imgbkp = f"{imgpath}.bkp"
    assert os.path.exists(imgbkp), "could not find backup: {}".format(imgbkp)

    print(f"[main] cwd: {os.getcwd()}")
    print(f"[main] mountpoint: {mountpoint}")
    print(f"[main] restoring {imgpath} from {imgbkp}")
    shutil.copy(imgbkp, imgpath)

    ready_event = threading.Event()
    stop_event = threading.Event()

    fs_thread = threading.Thread(
        target=run_filesystem,
        args=(mountpoint, ready_event, stop_event),
        daemon=True
    )

    test_thread = threading.Thread(
        target=run_tests,
        args=(args.test, mountpoint, ready_event, stop_event),
        daemon=True
    )

    fs_thread.start()
    test_thread.start()

    test_thread.join()
    stop_event.set()
    fs_thread.join()

    # Try to unmount (Linux)
    print("[main] unmounting...")
    subprocess.run(["fusermount", "-u", mountpoint],
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)

    shutil.rmtree(mountpoint)
    print("[main] done")


