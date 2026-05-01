on run
    set pythonRunning to false
    try
        tell application "System Events"
            set pythonRunning to (name of processes) contains "Python"
        end tell
    end try

    if pythonRunning then
        tell application "Python" to activate
        return
    end if

    do shell script "cd /Users/gd/Desktop/草莓订单管理系统 && export PYTHONPATH=/Users/gd/Desktop/草莓订单管理系统/src QT_QPA_PLATFORM=cocoa && if [ -x /Users/gd/Desktop/草莓订单管理系统/.venv/bin/python ]; then nohup /Users/gd/Desktop/草莓订单管理系统/.venv/bin/python -m strawberry_order_management.app >/tmp/strawberry-launcher.log 2>&1 </dev/null & else nohup /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m strawberry_order_management.app >/tmp/strawberry-launcher.log 2>&1 </dev/null & fi"
    delay 1
    try
        tell application "Python" to activate
    end try
end run
