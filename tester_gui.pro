#-------------------------------------------------
#
# Project created by QtCreator 2015-12-10T13:29:28
#
#-------------------------------------------------

QT       += core gui

greaterThan(QT_MAJOR_VERSION, 4): QT += widgets

TARGET = tester_gui
TEMPLATE = app

FORMS    += mainwindow.ui

OTHER_FILES += \
    tester.py \
    bts_test.py \
    bts_params.py \
    scpi/devices/__init__.py \
    scpi/devices/cmd57.py \
    scpi/devices/cmd57_console.py \
    scpi/devices/hp6632b.py \
    scpi/errors/__init__.py \
    scpi/transports/__init__.py \
    scpi/transports/baseclass.py \
    scpi/transports/rs232.py \
    scpi/__init__.py \
    scpi/scpi.py \
    scpi/serial_monitor.py
