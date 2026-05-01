#import <AppKit/AppKit.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <unistd.h>

static const char *REPO_DIR = "/Users/gd/Desktop/草莓订单管理系统";
static const char *SRC_DIR = "/Users/gd/Desktop/草莓订单管理系统/src";
static const char *PYTHON_BIN = "/Applications/Xcode.app/Contents/Developer/usr/bin/python3";
static const char *LOG_PATH = "/tmp/strawberry-launcher.log";
static const char *RUNNING_PATTERN = "strawberry_order_management\\.app";

static void write_log(const char *fmt, ...) {
    FILE *fp = fopen(LOG_PATH, "a");
    if (!fp) {
        return;
    }
    va_list args;
    va_start(args, fmt);
    vfprintf(fp, fmt, args);
    va_end(args);
    fputc('\n', fp);
    fclose(fp);
}

static pid_t find_running_pid(void) {
    char command[512];
    snprintf(
        command,
        sizeof(command),
        "pgrep -f '%s' | head -n 1",
        RUNNING_PATTERN
    );
    FILE *pipe = popen(command, "r");
    if (!pipe) {
        write_log("find_running_pid popen failed");
        return 0;
    }
    char buffer[64] = {0};
    char *line = fgets(buffer, sizeof(buffer), pipe);
    pclose(pipe);
    if (!line) {
        return 0;
    }
    pid_t pid = (pid_t)strtol(buffer, NULL, 10);
    write_log("find_running_pid pid=%d", (int)pid);
    return pid;
}

static void activate_running_pid(pid_t pid) {
    if (pid <= 0) {
        write_log("activate_running_pid skipped pid=%d", (int)pid);
        return;
    }
    @autoreleasepool {
        NSRunningApplication *app =
            [NSRunningApplication runningApplicationWithProcessIdentifier:pid];
        if (!app) {
            write_log("activate_running_pid no app for pid=%d", (int)pid);
            return;
        }
        BOOL activated =
            [app activateWithOptions:(NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps)];
        write_log("activate_running_pid pid=%d activated=%d", (int)pid, activated ? 1 : 0);
    }
}

static void launch_python_app(void) {
    pid_t pid = fork();
    write_log("launch_python_app fork pid=%d", (int)pid);
    if (pid != 0) {
        return;
    }

    if (chdir(REPO_DIR) != 0) {
        write_log("child chdir failed");
        _exit(120);
    }

    setenv("PYTHONPATH", SRC_DIR, 1);
    setenv("QT_QPA_PLATFORM", "cocoa", 1);
    write_log("child env set PYTHONPATH=%s", SRC_DIR);

    int log_fd = open(LOG_PATH, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (log_fd >= 0) {
        dup2(log_fd, STDOUT_FILENO);
        dup2(log_fd, STDERR_FILENO);
        close(log_fd);
    }

    int null_fd = open("/dev/null", O_RDONLY);
    if (null_fd >= 0) {
        dup2(null_fd, STDIN_FILENO);
        close(null_fd);
    }

    write_log("child execl python=%s", PYTHON_BIN);
    execl(
        PYTHON_BIN,
        "python3",
        "-m",
        "strawberry_order_management.app",
        (char *)NULL
    );
    write_log("child execl failed");
    _exit(127);
}

int main(void) {
    pid_t running_pid = find_running_pid();
    if (running_pid > 0) {
        write_log("main existing app detected; activating pid=%d", (int)running_pid);
        activate_running_pid(running_pid);
        return 0;
    }

    launch_python_app();
    usleep(1200 * 1000);
    running_pid = find_running_pid();
    write_log("main activation after launch pid=%d", (int)running_pid);
    activate_running_pid(running_pid);
    return 0;
}
