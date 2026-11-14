uid=$(id -u ginkgo)
sudo -u ginkgo XDG_RUNTIME_DIR=/run/user/$uid \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus \
     busctl --user get-property org.kde.kscreenlocker /MainApplication org.kde.KScreenLocker.MainApplication isLocked 2>/dev/null
sudo -u ginkgo XDG_RUNTIME_DIR=/run/user/$uid \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus \
     qdbus org.kde.KWin /KWin org.kde.KWin.supportInformation 2>/dev/null | head -n 30
