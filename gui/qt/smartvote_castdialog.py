from threading import Thread

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from electrum_smart.i18n import _
from electrum_smart.util import print_error, PrintError

class cast_vote_function(QObject):
    def __init__(self, widget):
        super(cast_vote_function, self).__init__()
        self.widget = widget
        self.run_trigger.connect(self.run)

    run_trigger = pyqtSignal(int, int)
    @pyqtSlot(int, int)
    def run(self, int1, int2):
        print_error("Vote started")
        self.cast_vote()
        print_error("Vote finished")
        #self.widget.someTrigger.emit([1, 2, 3])

    def cast_vote(self):
        selected_addresses = self.widget.manager.selected_addresses

        msg = 'Signing <b>{}</b> messages for <b>{}</b> proposal<br />'.format(
            len(selected_addresses) * len(self.widget.selected_proposals), len(self.widget.selected_proposals))
        self.widget.results.append(msg)

        for proposal_id in self.widget.selected_proposals:
            self.widget.results.append("Vote <b>{}</b> with <b>{} addresses</b> for proposal <b>#{}</b>".format(self.widget.selected_proposals[proposal_id], len(selected_addresses), proposal_id))
            self.widget.results.append("<br />Waiting for response.<br />")
            final_results = self.widget.manager.cast_vote(proposal_id, self.widget.selected_proposals[proposal_id],selected_addresses, self.widget.password)

            self.widget.results.append('Result for proposal <b>#{}</b>'.format(proposal_id))
            for result in final_results:
                if result["status"] == "OK":
                    status = '<span style=\" color:green; \"><b>OK</b></span>'
                else:
                    status = '<span style=\" color:red; \">{}</span>'.format(result["status"])
                self.widget.results.append('-> {} | {} SMART <b>{}</b>'.format(result["smartAddress"], int(result["amount"]), status))

        msg = '<br /><b>Done!</b>'
        self.widget.results.append(msg)


class CastVotesDialog(QDialog, PrintError):

    def __init__(self, parent, manager, selected_proposals, password):
        super(CastVotesDialog, self).__init__(parent)
        self.manager = manager
        self.password = password
        self.selected_proposals = selected_proposals
        self.setupUi()
        self.start()

    def setupUi(self):
        self.setObjectName("CastVotesDialog")
        self.resize(900, 500)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(20, 20, 20, 20)
        self.verticalLayout.setObjectName("verticalLayout")
        self.results = QTextBrowser(self)
        self.results.setFrameShape(QFrame.NoFrame)
        self.results.setFrameShadow(QFrame.Plain)
        self.results.setObjectName("results")
        self.verticalLayout.addWidget(self.results)
        self.widget_2 = QWidget(self)
        self.widget_2.setMinimumSize(QSize(0, 0))
        self.widget_2.setObjectName("widget_2")
        self.horizontalLayout_2 = QHBoxLayout(self.widget_2)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem = QSpacerItem(89, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.button = QPushButton(self.widget_2)
        self.button.setObjectName("button")
        self.button.clicked.connect(self.close)
        self.horizontalLayout_2.addWidget(self.button)
        spacerItem1 = QSpacerItem(88, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.verticalLayout.addWidget(self.widget_2)

        self.retranslateUi(self)
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self, CastVotesDialog):
        _translate = QCoreApplication.translate
        self.setWindowTitle(_translate("CastVotesDialog", "Cast Vote"))
        self.results.setHtml(_translate("CastVotesDialog", "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" \"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
"<html><head><meta name=\"qrichtext\" content=\"1\" /><style type=\"text/css\">\n"
"p, li { white-space: pre-wrap; }\n"
"</style></head><body style=\" font-family:\'.SF NS Text\'; font-size:13pt; font-weight:400; font-style:normal;\">\n"
"<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;\"><span style=\" font-weight:600; color:#000000;\">Start voting...<br /></span></p></body></html>"))
        self.button.setText(_translate("CastVotesDialog", "Close"))


    def start(self):
        self.thread = QThread()
        self.thread.start()
        self.consume = cast_vote_function(self)
        self.consume.moveToThread(self.thread)
        self.consume.run_trigger.emit(1, 1)



