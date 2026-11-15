#!/bin/sh
# Clear legacy values inherited from SDDM as well as environment.d. KWin
# launches the selected Plasma Keyboard, which configures its own Qt engine.
unset QT_IM_MODULE QT_IM_MODULES
