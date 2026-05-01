on run
    do shell script "cd /Users/gd/Desktop/草莓订单管理系统 && nohup env PYTHONPATH=/Users/gd/Desktop/草莓订单管理系统/src QT_QPA_PLATFORM=cocoa /Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m strawberry_order_management.app >/tmp/strawberry-launcher.log 2>&1 </dev/null &"
    delay 1
    try
        tell application "Python" to activate
    end try
end run
