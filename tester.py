#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtCore import pyqtSlot, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QDialog, QListWidgetItem, QMessageBox
from PyQt5.uic import loadUiType
import time
import traceback
import socket
import serial
from scpi.errors import TimeoutError

import fwtp_core
import fwtp_engine

main_form, base_class = loadUiType('mainwindow.ui')

def get_html_color_tags(color):
    return ('<font color="%s">' % color, '</font>')

HTML_RESULT_MAPS = {
    fwtp_core.TEST_NA      : "%s    N/A%s" % get_html_color_tags("blue"),
    fwtp_core.TEST_ABORTED : "%sABORTED%s" % get_html_color_tags("magenta"),
    fwtp_core.TEST_OK      : "%s     OK%s" % get_html_color_tags("green"),
    fwtp_core.TEST_FAIL    : "%s   FAIL%s" % get_html_color_tags("red")
}

class MainWindowImpl(QMainWindow, main_form):
    def load_tests(self):
        for i in fwtp_core.TestSuiteConfig.KNOWN_TESTS_DESC.keys():
            ti = fwtp_core.TestSuiteConfig.KNOWN_TESTS_DESC[i]
            item = QListWidgetItem(ti.testname, self.listWidget)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setToolTip(ti.INFO)

    def load_testsuite(self):
        def new_test_decorator(path, ti, args):
            return self.on_test_visit(path, ti, args)

        fwtp_core.TestSuiteConfig.DECORATOR_DEFAULT = new_test_decorator
        self.texec = fwtp_engine.TestExecutor(open(self.testscript, "r").read())

    def __init__(self, app, testscript, *args):
        super(MainWindowImpl, self).__init__(*args)
        self.app = app

        self.setupUi(self)
        self.testscript = testscript
        self.load_testsuite()
        self.load_tests()
        self.started = False
        self.tests = {}
        self.tests_debug = True
        self.cbHosts.addItems(["manual", "local"])
        self.cbDevice.clear()

    def enable_controls(self, en):
        self.listWidget.setEnabled(en)
        self.btAll.setEnabled(en)
        self.btNone.setEnabled(en)
        self.btFind.setEnabled(en)
        self.cbHosts.setEnabled(en)
        self.lnPort.setEnabled(en)
        self.cbDevice.setEnabled(en)
        self.cbCh1.setEnabled(en)
        self.cbCh2.setEnabled(en)
        self.spArfcn.setEnabled(en)

    @pyqtSlot()
    def on_btStartStop_clicked(self):
        if self.started:
            self.aborted = True
            self.started = False
            self.on_stop()
            self.btStartStop.setText("Start")
            self.enable_controls(True)
        else:
            self.aborted = False
            self.started = True
            self.btStartStop.setText("Stop")
            self.enable_controls(False)
            self.test_ok = True

            #self.on_start()
            #return

            try:
                self.on_start()
            except serial.serialutil.SerialException as e:
                self.test_ok = False
                self.txConsole.appendHtml("<br><br><font color=\"red\">CMD57 exception:</font><br><b>%s</b>" %
                                            str(e))
             # scpi.errors.TimeoutError
            except:
                if self.tests_debug:
                    traceback.print_exc()
                self.test_ok = False
                self.txConsole.appendHtml("<br><br><font color=\"red\">Unknown exception:</font><br><b>%s</b>" %
                                            str(sys.exc_info()))
            finally:
                if not self.test_ok:
                    self.txConsole.appendHtml("<br><br><h2><font color=\"red\">TEST FAILED</font></h2>")
                elif not self.started:
                    self.txConsole.appendHtml("<br><br><h2><font color=\"yellow\">TEST ABORTED</font></h2>")
                else:
                    self.txConsole.appendHtml("<br><br><h2><font color=\"green\">TEST OK</font></h2>")
                self.btStartStop.setText("Start")
                self.enable_controls(True)
                self.started = False

    @pyqtSlot()
    def on_btFind_clicked(self):
        self.cbHosts.clear()
        self.cbHosts.addItems(["manual", "local"])
#        ips = subprocess.check_output('nmap -sP 192.168.1.0/24 | grep "Nmap scan report for "', shell=True).decode('utf-8').replace("Nmap scan report for ", "").split()
#        if len(ips) == 0:
#            self.txConsole.appendHtml("No hosts were found")
#            return

#        for ip in ips:
#            QApplication.processEvents()
#            try:
#                b = bts_test.BtsControlSsh(ip, 22)
#                u = b.get_uname()
#                s = b.get_umtrx_eeprom_val("serial")
#                self.txConsole.appendHtml("Host <b>%s</b> - <i>%s</i> - %s" % (ip, u, s))
#                self.cbHosts.addItem(ip)

#            except ConnectionRefusedError:
#                self.txConsole.appendHtml("Host %s is unreachable" % ip)
#            except socket.timeout:
#                self.txConsole.appendHtml("Host %s connection timed out" % ip)


    @pyqtSlot()
    def on_btAll_clicked(self):
        self.set_to_all_tests(True)

    @pyqtSlot()
    def on_btNone_clicked(self):
        self.set_to_all_tests(False)

    @pyqtSlot()
    def on_btBlink_clicked(self):
        pass
        ################### bts = self.create_bts()
        ################### bts.bts_led_blink(1)
        ################### QMessageBox.question(self, 'LED Blinking',
        ###################                    'LED is blinking on "%s"\nPress OK to stop blinking' % self.cbHosts.currentText(), QMessageBox.Ok)
        ################### bts.bts_led_on()

    def set_to_all_tests(self, en=True):
        s = Qt.Checked if en else Qt.Unchecked
        for i in range(self.listWidget.count()):
            self.listWidget.item(i).setCheckState(s)

    def on_test_visit(self, path, ti, kwargs):
        testname = "%s/%s" % (path, ti.testname)
        func = ti.func

        self.app.processEvents()
        if not self.started:
            self.txConsole.appendHtml("<pre>[%s] <font color=\"red\">Aborting   %60s</font></pre>" % (
                                      self.get_ts(),testname))
            return fwtp_core.TEST_ABORTED

        if not self.tests[ti.testname]:
            self.txConsole.appendHtml("<pre>[%s] <font color=\"red\">Skipping   %60s</font></pre>" % (
                                      self.get_ts(),testname))
            return fwtp_core.TEST_NA

        self.txConsole.appendHtml("<pre>[%s] <font color=\"blue\">Executing  %60s</font></pre>" % (
                                  self.get_ts(),testname))
        try:
            val = func(kwargs)
            res = self.tr.check_test_result(path, ti, val, **kwargs)
        except TimeoutError as e:
            res = fwtp_core.TEST_FAIL
            self.tr.set_test_result(path, ti, res)
            self.txConsole.appendHtml("<pre>[%s] <font color=\"red\">Timeout (%s) %60s</font></pre>" % (
                                      self.get_ts(), e, testname))
        except:
            if self.tests_debug:
                traceback.print_exc()
            res = fwtp_core.TEST_ABORTED
            self.tr.set_test_result(path, ti, res)
        return res

    def on_start(self):
        QApplication.processEvents()
        self.tests = { self.listWidget.item(i).text():
            self.listWidget.item(i).checkState() == Qt.Checked for i in range(len(fwtp_core.TestSuiteConfig.KNOWN_TESTS_DESC.keys())) }

        dut = self.cbDevice.currentText()
        arfcn=int(self.spArfcn.value())

        # Initialize test results structure
        self.tr = MyTestResults(self.on_test_result, self.on_test_progress, self.on_enter_bundle)

        self.args = {
            "DUT"       : dut,
            "ARFCN"     : arfcn,
            "BTS_IP"    : self.cbHosts.currentText(),
            "CMD57_PORT": self.lnPort.text(),
            "TR"        : self.tr,
            "UI"        : self,
            "CHAN"      : ""
            }

        self.texec.run(self.args)

        sm = self.tr.summary()
        for res in sm:
            self.txConsole.appendHtml("<pre>%s: %2d</pre>" % (HTML_RESULT_MAPS[res], sm[res]))
        failed = sm.setdefault(fwtp_core.TEST_NA, 0) + sm.setdefault(fwtp_core.TEST_ABORTED, 0) + sm.setdefault(fwtp_core.TEST_FAIL, 0)
        if failed > 0:
            self.txConsole.appendHtml("<br>%s<h1>WARNING! NOT ALL TEST PASSED!</h1>%s<br>" % get_html_color_tags("red"))
            if self.started:
                self.test_ok = False
            else:
                return #Don't wirte JSON in case of abort

        test_id = str(self.args["TEST_ID"]) if "TEST_ID" in self.args else None
        if test_id is not None:
            f = open("out/bts-test."+test_id+".json", 'w')
            f.write(self.tr.json())
            f.close()
        else:
            self.txConsole.appendHtml("<br>%sTEST_ID variable wasn't declared during test, skiping writing results" % get_html_color_tags("red"))

    def on_stop(self):
        self.txConsole.appendPlainText("ABORT requested")
        QApplication.processEvents()

    def ask(self, text):
        QApplication.processEvents()
        if self.aborted:
            return False
        reply = QMessageBox.question(self, 'Message',
                    text, QMessageBox.Ok |
                    QMessageBox.Cancel, QMessageBox.Ok)
        if reply == QMessageBox.Ok:
            return True

        #self.started = False
        #self.on_stop()
        return False

    def on_enter_bundle(self, t, path, bundle, disc):
        QApplication.processEvents()
        tcolot = get_html_color_tags("blue")
        self.txConsole.appendHtml("<pre>[%s] Bundle %s<b>%50s</b>%s:  %s</pre>" % (
            self.get_ts(t),
            tcolot[0],
            "%s/%s" % (path, bundle),
            tcolot[1],
            disc))
        QApplication.processEvents()

    def on_test_result(self, t, path, ti, result, value, old_result, old_value, delta, reason=None):
        if old_result == result or old_result is None:
            tcolot = ("","")
        elif old_result != fwtp_core.TEST_OK and result == fwtp_core.TEST_OK:
            tcolot = get_html_color_tags("green")
        elif old_result == fwtp_core.TEST_OK and result != fwtp_core.TEST_OK:
            tcolot = get_html_color_tags("red")
        else:
            tcolot = get_html_color_tags("orange")

        sdelta = " [%+f]" % delta if delta is not None else ""
        was=" (%7s)%s" % (HTML_RESULT_MAPS[old_result], sdelta) if old_result is not None else ""
        exr = "" if reason is None else " (%s)" % reason
        self.txConsole.appendHtml("<pre>[%s] %s<b>%50s</b>%s:  %s %s%s %s</pre>" % (
            self.get_ts(t),
            tcolot[0],
            ti.INFO,
            tcolot[1],
            HTML_RESULT_MAPS[result],
            was,
            exr,
            "" if value is None else str(value)))

    def get_ts(self, t = None):
        if t is None:
            t = time.time()
        return time.strftime("%d-%m-%Y %H:%M:%S", time.localtime(t))

    def on_test_progress(self, str):
        QApplication.processEvents()
        self.txConsole.appendHtml("<pre>%s</pre>" % str)
        QApplication.processEvents()

class MyTestResults(fwtp_engine.TestResults):
    def __init__(self, proxyfn, output_progressfn, enter_bundlefn):
        super().__init__()
        self.proxyfn = proxyfn
        self.output_progressfn = output_progressfn
        self.enter_bundlefn = enter_bundlefn

    def print_result(self, t, path, ti, result, value, old_result, old_value, delta, reason=None):
        self.proxyfn(t, path, ti, result, value, old_result, old_value, delta, reason)

    def output_progress(self, string):
        self.output_progressfn(string)

    def enter_bundle(self, t, path, bundle, disc):
        self.enter_bundlefn(t, path, bundle, disc)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fwtp_engine.TestExecutor.trace_calls = True

    import testsuite_bts
    main = MainWindowImpl(app, "./oc.yaml")
    main.show()

    sys.exit(app.exec_())

