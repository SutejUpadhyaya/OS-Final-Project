#!/usr/bin/env python3
import os
import subprocess
import threading
import time
import tempfile
import shutil
import signal
import sys
import stat
import errno

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

    # overwrite with same length content
    same = "xyz xyz xyz xyz xyz xyz xyz"
    with open(file_path, "w") as file_open:
        file_open.write(same)
    print("[test] overwrote file with same length content (" + str(len(same)) + " bytes)")

    # check size shrunk correctly
    with open(file_path, "r") as file_open:
        data = file_open.read()
    status = os.stat(file_path)
    if status.st_size != len(same):
        assert_text = "wrong size after same length overwrite: expected " + str(len(same)) + ", got " + str(status.st_size) + "; contents of file: expected " + repr(same) + ", got " + repr(data)
        assert False, assert_text

    # check contents are fully replaced (no leftover bytes)
    if data != same:
        assert_text = "wrong content after same length overwrite: expected " + repr(same) + ", got " + repr(data)
        assert False, assert_text
    print("[test] same length overwrite successful")

    # overwrite with shorter content
    shorter = "def"
    with open(file_path, "w") as file_open:
        file_open.write(shorter)
    print("[test] overwrote file with shorter content (" + str(len(shorter)) + " bytes)")

    # check size shrunk correctly
    with open(file_path, "r") as file_open:
        data = file_open.read()
    status = os.stat(file_path)
    if status.st_size != len(shorter):
        assert_text = "wrong size after shorter overwrite: expected " + str(len(shorter)) + ", got " + str(status.st_size) + "; contents of file: expected " + repr(shorter) + ", got " + repr(data)
        assert False, assert_text

    # check contents are fully replaced (no leftover bytes)
    if data != shorter:
        assert_text = "wrong content after shorter overwrite: expected " + repr(shorter) + ", got " + repr(data)
        assert False, assert_text
    print("[test] shorter overwrite successful")

    # overwrite with longer content
    longer = "ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi ghi"
    with open(file_path, "w") as file_open:
        file_open.write(longer)
    print("[test] overwrote with longer content (" + str(len(longer)) + " bytes)")

    # check size grew
    status = os.stat(file_path)
    if status.st_size != len(longer):
        assert_text = "wrong size after longer overwrite: expected " + str(len(longer)) + ", got " + str(status.st_size) + "; contents of file: " + repr(data)
        assert False, assert_text

    # check contents
    with open(file_path, "r") as file_open:
        data = file_open.read()
    if data != longer:
        assert_text = "wrong content after longer overwrite: expected " + repr(longer) + ", got " + repr(data)
        assert False, assert_text
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

def test_link(mountpoint):
    # counting hard links
    src = os.path.join(mountpoint, "hello.txt")
    link = os.path.join(mountpoint, "link.txt")
    with open(src,'w') as f:
         f.write("link test content")
    if os.stat(src).st_nlink != 1:
        assert False, "expected nlink=1 before link, got " + str(os.stat(src).st_nlink)
    os.link(src,link)

    time.sleep(1.5)  # wait for FUSE attr cache to expire
    if os.stat(src).st_nlink != 2:
        assert False, "expected src nlink=2 after link, got " + str(os.stat(src).st_nlink)
    if os.stat(link).st_nlink != 2:
        assert False, "expected link nlink=2 after link, got " + str(os.stat(link).st_nlink)
    os.unlink(link)

    time.sleep(1.5)  # wait for FUSE attr cache to expire
    if os.stat(src).st_nlink != 1:
        assert False, "expected nlink=1 after unlink, got " + str(os.stat(src).st_nlink)
    os.remove(src)
    print("[test] passed hard link and unlink count")

def test_update_access_mod_time(mountpoint):
    # update access/modification time

    file_path = os.path.join(mountpoint, "utimens_test.txt")

    # create initial file
    with open(file_path, "w") as file_open:
        file_open.write("initial content\n")
    print("[test] created file " + file_path)

    time.sleep(2)

    # set explicit atime/mtime far in the past
    past_atime = 1000000000.0
    past_mtime = 1000000001.0
    os.utime(file_path, (past_atime, past_mtime))
    print("[test] initial atime==" + str(past_atime) + ", mtime=" + str(past_mtime))

    status1 = os.stat(file_path)
    if abs(status1.st_atime - past_atime) >= 2:
        assert False, "atime not set: expected ~" + str(past_atime) + ", got " + str(status1.st_atime)
    if abs(status1.st_mtime - past_mtime) >= 2:
        assert False, "mtime not set: expected ~" + str(past_mtime) + ", got " + str(status1.st_mtime)
    print("[test] atime/mtime correctly stored after explicit utime")

    # write should update mtime (and not leave mtime at the past value)
    time.sleep(0.1)
    before_write = time.time()

    # modifying file, should update mtime
    with open(file_path, "w") as file_open:
        file_open.write("modified content\n")
    after_write = time.time()

    status2 = os.stat(file_path)
    print("[test] after write mtime=" + str(status2.st_mtime))

    if status2.st_mtime < before_write - 1:
        assert False, "mtime not advanced after write: got " + str(status2.st_mtime) + ", expected >= " + str(before_write)
    if status2.st_mtime > after_write + 2:
        assert False, "mtime too far in future after write: got " + str(status2.st_mtime)
    print("[test] mtime advanced correctly after write")


    # set a new explicit pair and verify both change independently
    new_atime = 1111111111.0  # 2005-03-18
    new_mtime = 1222222222.0  # 2008-09-23
    os.utime(file_path, (new_atime, new_mtime))
    status3 = os.stat(file_path)
    if abs(status3.st_atime - new_atime) >= 2:
        assert False, "atime wrong after second utime: expected ~" + str(new_atime) + ", got " + str(status3.st_atime)
    if abs(status3.st_mtime - new_mtime) >= 2:
        assert False, "mtime wrong after second utime: expected ~" + str(new_mtime) + ", got " + str(status3.st_mtime)
    print("[test] second explicit utime preserved both timestamps independently")

    # clean up
    os.remove(file_path)
    if os.path.exists(file_path):
        assert False, "failed to delete utimens_test.txt"

    print("[test] passed utimens")


def test_chmod(mountpoint):
    # changing permissions
    file_path = os.path.join(mountpoint,"chmod_test.txt")
    # 777 = 111111111 (RWX for all)

    # create file
    with open(file_path,'w') as f:
        f.write("chmod_test\n")
    print("[test] created file " + file_path)
    
    os.chmod(file_path, 0o700)
    # 111 000 000
    # RWX for owner
    if ((os.stat(file_path).st_mode & 0o777) != 0o700): # bitwise comparison to check for correct permissions
        assert False, "chmod failed: expected the perms 700, got " + oct(os.stat(file_path).st_mode & 0o777)
    
    os.chmod(file_path,0o644)
    # 110 100 100
    # R for all, W for owner
    if ((os.stat(file_path).st_mode & 0o777) != 0o644):
        assert False, "chmod failed: expected the perms 644, got " + oct(os.stat(file_path).st_mode & 0o777)

    # cleanup
    os.remove(file_path)
    if os.path.exists(file_path):
        assert False, "failed to delete chmod_test.txt"
    
    # creates directory
    dir_path = os.path.join(mountpoint,"chmoddir")
    os.mkdir(dir_path)
    
    os.chmod(dir_path,0o755)
    # 111 101 101
    # RX for all, W for owner
    if((os.stat(dir_path).st_mode & 0o777) != 0o755):
        assert False, "chmod failed: expected the perms 755, got " + oct(os.stat(dir_path).st_mode & 0o777)
    
    # cleanup
    os.rmdir(dir_path)
    if os.path.exists(dir_path):
        assert False, "failed to delete chmoddir"
    
    print("[test] passed chmod")


#  expect error when opening a write-only file for reading
def test_access_open_w_only_for_r(mountpoint):
    file_path = os.path.join(mountpoint,"write_only.txt")
    with open(file_path, 'w') as f:
        f.write("some content")
    os.chmod(file_path, stat.S_IWUSR)
    err = False
    try:
        #try except to catch the error
        # attempts opens a write-only file
        with open(file_path,'r') as f:
            f.read()# will never reach as it will err on open
    except PermissionError: 
       # permission error  as they have the wrong permissions to use the file
       # cited source https://docs.python.org/3/library/exceptions.html
       err = True
    assert err, "expected error when opening write-only file for reading"
    os.chmod(file_path, 0o644)
    os.remove(file_path)
    #removes file and checks if it is delted
    if(os.path.exists(file_path)):
        assert False, "failed to delete write_only.txt"

    print("[test] passed, not allowed to open a write-only file for reading")

#  expect error when opening a read-only file for writing
def test_access_open_r_only_for_w(mountpoint):
    file_path = os.path.join(mountpoint,"read_only.txt")
    with open(file_path, 'w') as f:
        f.write("some content")
    os.chmod(file_path, stat.S_IRUSR)
    err = False
    try:
        #try except to catch the error
        # ttempts opens a read-only file
        with open(file_path,"w") as f:
            f.write("should not be able to write")
            #will never reach this write as it  errs on open
    except PermissionError:
        # permission error  as they have the wrong permissions to use the file
        err = True
    assert err, "expected error when opening read-only file for writing"
    os.chmod(file_path, 0o644)
    os.remove(file_path)
    #removes file and checks if it is delted
    if(os.path.exists(file_path)):
        assert False, "failed to delete write_only.txt"
    
    print("[test] passed, not allowed to open a read-only file for writing")

#  expect error when reading from a file opened as write-only
def test_access_r_from_w_only(mountpoint):
    file_path = os.path.join(mountpoint,"write_only.txt")
    with open(file_path, 'w') as f:
        f.write("some content")
    
    fd = os.open(file_path, os.O_WRONLY)

    err = False
    try:
        #try except to catch the error
        # open and read a write-only file
        os.read(fd, 100) # errs on this read so goes to except
    except OSError as e:
        if e.errno == errno.EBADF: # bad file handle error
            err = True
    finally:
        # close fd always
        os.close(fd)

    assert err, "expected error when reading from a file opened as write-only"

    #removes file and checks if it is delted
    os.remove(file_path)
    if(os.path.exists(file_path)):
        assert False, "failed to delete write_only.txt"
    
    print("[test] passed, not allowed to read a write-only file")

#  expect error when writing to a file opened as read-only
def test_access_w_from_r_only(mountpoint):
    file_path = os.path.join(mountpoint,"read_only.txt")
    with open(file_path, 'w') as f:
        f.write("some content")

    fd = os.open(file_path, os.O_RDONLY)

    err = False
    try:   
        #try except to catch the error
        # opens a read-only file
        os.write(fd, b"this should fail") # errs on this write so goes to except
    except OSError as e:
        if e.errno == errno.EBADF: # bad file handle error
            err = True
    finally:
        # close fd always
        os.close(fd)

    assert err, "expected error when writing from a file opened as read-only"

    #removes file and checks if it is delted
    os.remove(file_path)
    if(os.path.exists(file_path)):
        assert False, " failed to delete read_only.txt"

    print("[test] passed, not allowed to write to a read-only file")

##############################################################################
# END TEST DEFINITIONS
##############################################################################

TESTS = { # from Max Green on the 492 discord
    k.removeprefix('test_'): v for k, v in globals().items() if k.startswith('test_')
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


