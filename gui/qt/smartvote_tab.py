import os
import traceback

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

from electrum_smart import bitcoin, keystore
from .smartvote_listproposal import Ui_SmartProposalWidget
from electrum_smart.util import print_error, print_msg
from electrum_smart.smartvote_manager import SmartvoteManager
from .smartvote_castdialog import CastVotesDialog
from .smartvote_addresses import VoteAddressesDialog

from . import util

class SmartvoteTab(QWidget):

    def __init__(self, parent=None):
        super(SmartvoteTab, self).__init__(parent)
        self.gui = parent
        self.selected_voting_option_map = dict()
        self.create_layout()
        self.on_proposal_option_changed()
        self.open_proposals_qty = 0
        self.smartvote_manager = None
        self.vote_address_list = None

    def create_layout(self):
        self.setObjectName("SmartVotingPage")
        self.resize(811, 457)
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.stackedWidget = QStackedWidget(self)
        self.stackedWidget.setMaximumSize(QSize(16777215, 16777215))
        self.stackedWidget.setObjectName("stackedWidget")
        self.page = QWidget()
        self.page.setObjectName("page")
        self.verticalLayout_3 = QVBoxLayout(self.page)
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.stackedWidget.addWidget(self.page)
        self.loadingPage = QWidget()
        self.loadingPage.setObjectName("loadingPage")
        self.verticalLayout_7 = QVBoxLayout(self.loadingPage)
        self.verticalLayout_7.setObjectName("verticalLayout_7")
        self.stackedWidget.addWidget(self.loadingPage)
        self.rewardsPage = QWidget()
        self.rewardsPage.setMinimumSize(QSize(0, 0))
        self.rewardsPage.setMaximumSize(QSize(16777215, 16777215))
        self.rewardsPage.setObjectName("rewardsPage")
        self.verticalLayout_2 = QVBoxLayout(self.rewardsPage)
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.widget_2 = QWidget(self.rewardsPage)
        self.widget_2.setMinimumSize(QSize(0, 60))
        self.widget_2.setObjectName("widget_2")
        self.horizontalLayout_5 = QHBoxLayout(self.widget_2)
        self.horizontalLayout_5.setContentsMargins(-1, 0, -1, 0)
        self.horizontalLayout_5.setObjectName("horizontalLayout_5")
        self.verticalLayout_5 = QVBoxLayout()
        self.verticalLayout_5.setObjectName("verticalLayout_5")
        self.horizontalLayout_12 = QHBoxLayout()
        self.horizontalLayout_12.setObjectName("horizontalLayout_12")
        self.label_17 = QLabel(self.widget_2)
        font = QFont()
        font.setPointSize(14)
        self.label_17.setFont(font)
        self.label_17.setObjectName("label_17")
        self.horizontalLayout_12.addWidget(self.label_17)
        self.openProposalsLabel = QLabel(self.widget_2)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.openProposalsLabel.sizePolicy().hasHeightForWidth())
        self.openProposalsLabel.setSizePolicy(sizePolicy)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(75)
        self.openProposalsLabel.setFont(font)
        self.openProposalsLabel.setObjectName("openProposalsLabel")
        self.horizontalLayout_12.addWidget(self.openProposalsLabel)
        self.verticalLayout_5.addLayout(self.horizontalLayout_12)
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label_18 = QLabel(self.widget_2)
        font = QFont()
        font.setPointSize(14)
        self.label_18.setFont(font)
        self.label_18.setObjectName("label_18")
        self.horizontalLayout.addWidget(self.label_18)
        self.votedForLabel = QLabel(self.widget_2)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.votedForLabel.sizePolicy().hasHeightForWidth())
        self.votedForLabel.setSizePolicy(sizePolicy)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(75)
        self.votedForLabel.setFont(font)
        self.votedForLabel.setObjectName("votedForLabel")
        self.horizontalLayout.addWidget(self.votedForLabel)
        self.verticalLayout_5.addLayout(self.horizontalLayout)
        self.horizontalLayout_5.addLayout(self.verticalLayout_5)
        self.verticalLayout_8 = QVBoxLayout()
        self.verticalLayout_8.setSpacing(4)
        self.verticalLayout_8.setObjectName("verticalLayout_8")
        self.horizontalLayout_3 = QHBoxLayout()
        self.horizontalLayout_3.setObjectName("horizontalLayout_3")
        self.votingPower = QLabel(self.widget_2)
        font = QFont()
        font.setPointSize(14)
        self.votingPower.setFont(font)
        self.votingPower.setObjectName("votingPower")
        self.horizontalLayout_3.addWidget(self.votingPower)
        self.votingPowerLabel = QLabel(self.widget_2)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        font.setWeight(75)
        self.votingPowerLabel.setFont(font)
        self.votingPowerLabel.setObjectName("votingPowerLabel")
        self.horizontalLayout_3.addWidget(self.votingPowerLabel)
        self.verticalLayout_8.addLayout(self.horizontalLayout_3)
        self.horizontalLayout_6 = QHBoxLayout()
        self.horizontalLayout_6.setObjectName("horizontalLayout_6")
        self.addressesLabel = QLabel(self.widget_2)
        self.addressesLabel.setObjectName("addressesLabel")
        self.horizontalLayout_6.addWidget(self.addressesLabel)

        self.selectAddressesButton = QPushButton(self.widget_2)
        self.selectAddressesButton.setObjectName("selectAddressesButton")
        self.selectAddressesButton.clicked.connect(self.open_addresses_dialog)

        self.horizontalLayout_6.addWidget(self.selectAddressesButton)
        self.verticalLayout_8.addLayout(self.horizontalLayout_6)
        self.horizontalLayout_5.addLayout(self.verticalLayout_8)
        self.verticalLayout_2.addWidget(self.widget_2)
        self.scrollArea = QScrollArea(self.rewardsPage)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.proposalList = QWidget()
        self.proposalList.setGeometry(QRect(0, 0, 791, 339))
        self.proposalList.setObjectName("proposalList")
        self.verticalLayout_6 = QVBoxLayout(self.proposalList)
        self.verticalLayout_6.setContentsMargins(9, -1, 9, -1)
        self.verticalLayout_6.setSpacing(8)
        self.verticalLayout_6.setObjectName("verticalLayout_6")
        self.scrollArea.setWidget(self.proposalList)
        self.verticalLayout_2.addWidget(self.scrollArea)
        self.horizontalLayout_2 = QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem)
        self.refreshButton = QPushButton(self.rewardsPage)
        self.refreshButton.setObjectName("refreshButton")
        self.refreshButton.clicked.connect(self.refresh_proposals)
        self.horizontalLayout_2.addWidget(self.refreshButton)
        spacerItem1 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem1)
        self.castVotesButton = QPushButton(self.rewardsPage)
        self.castVotesButton.setObjectName("castVotesButton")
        self.castVotesButton.clicked.connect(self.open_cast_vote_dialog)
        self.horizontalLayout_2.addWidget(self.castVotesButton)
        spacerItem2 = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.horizontalLayout_2.addItem(spacerItem2)
        self.verticalLayout_2.addLayout(self.horizontalLayout_2)
        self.stackedWidget.addWidget(self.rewardsPage)
        self.verticalLayout.addWidget(self.stackedWidget)

        self.retranslateUi(self)
        self.stackedWidget.setCurrentIndex(2)
        QMetaObject.connectSlotsByName(self)

    def retranslateUi(self, SmartVotingPage):
        _translate = QCoreApplication.translate
        self.setWindowTitle(_translate("SmartVotingPage", "Form"))
        self.label_17.setText(_translate("SmartVotingPage", "Open proposals"))
        self.openProposalsLabel.setText(_translate("SmartVotingPage", "0"))
        self.label_18.setText(_translate("SmartVotingPage", "You voted for"))
        self.votedForLabel.setText(_translate("SmartVotingPage", "0"))
        self.votingPower.setText(_translate("SmartVotingPage", "Selected voting power"))
        self.votingPowerLabel.setText(_translate("SmartVotingPage", "0 SMART"))
        self.addressesLabel.setText(_translate("SmartVotingPage", "( 0 addresses )"))
        self.selectAddressesButton.setText(_translate("SmartVotingPage", "Select addresses"))
        self.refreshButton.setText(_translate("SmartVotingPage", "Refresh List"))
        self.castVotesButton.setText(_translate("SmartVotingPage", "Vote for X proposals"))

    def open_addresses_dialog(self):
        d = VoteAddressesDialog(self.smartvote_manager)
        d.exec_()
        self.update_vote_info()

    def open_cast_vote_dialog(self):
        password = None
        if self.smartvote_manager.wallet.has_password():
             if isinstance(self.smartvote_manager.wallet.keystore, keystore.Hardware_KeyStore):
                 self.start_cast_vote_dialog(password)
                 return
             else:
                 password = self.gui.password_dialog('Please enter your password to vote')
                 if password is None:
                     return
                 else:
                     try:
                         self.smartvote_manager.wallet.check_password(password)
                     except:
                         self.gui.show_warning('Incorrect password')
                         return
                     self.start_cast_vote_dialog(password)
        else:
            self.start_cast_vote_dialog(password)


    def start_cast_vote_dialog(self, password):
        d = CastVotesDialog(self.gui, self.smartvote_manager, self.selected_voting_option_map, password)
        d.exec_()
        self.refresh_proposals()

    def on_proposal_option_changed(self):
        selected_proposals = len(self.selected_voting_option_map)
        self.castVotesButton.setText("Vote for {} proposals".format(selected_proposals))
        if selected_proposals > 0:
            self.castVotesButton.setEnabled(True)
        else:
            self.castVotesButton.setEnabled(False)

    def load_smartvote(self, smartvotemanager):
        self.smartvote_manager = smartvotemanager
        self.update_vote_info()

    def update_vote_info(self):
        voting_power = self.smartvote_manager.get_voting_power()
        voting_power_label = "{} SMART".format(self.smartvote_manager.add_thousands_spaces(voting_power))
        self.votingPowerLabel.setText(voting_power_label)
        addresses_label = "( {} addresses )".format(len(self.smartvote_manager.selected_addresses))
        self.addressesLabel.setText(addresses_label)
        if(len(self.smartvote_manager.avaliable_addresses) == 0):
            self.selectAddressesButton.setEnabled(False)

    def update_all_proposals(self):
        if self.open_proposals_qty <= 0:
            util.WaitingDialog(self, ('Loading proposals...'), self.load_proposal_thread, self.on_load_proposal_successful, self.on_load_proposal_error)

    def load_proposal_thread(self):
        self.smartvote_manager.update_proposals()

    def on_load_proposal_successful(self, result):
        open_proposals = self.smartvote_manager.proposals
        self.open_proposals_qty = len(open_proposals)
        self.openProposalsLabel.setText(str(self.open_proposals_qty))

        for proposal in open_proposals:
            SmartProposalWidget = QWidget()
            ui = Ui_SmartProposalWidget()
            ui.setupUi(SmartProposalWidget, proposal, self.selected_voting_option_map, self.smartvote_manager)
            ui.yesButton.clicked.connect(self.on_proposal_option_changed)
            ui.noButton.clicked.connect(self.on_proposal_option_changed)
            ui.abstainButton.clicked.connect(self.on_proposal_option_changed)
            ui.disabledButton.clicked.connect(self.on_proposal_option_changed)
            self.verticalLayout_6.addWidget(SmartProposalWidget)

        self.votedForLabel.setText(str(self.smartvote_manager.voted_proposals))
        print_msg('Successfully loaded proposals')

    def on_load_proposal_error(self, err):
        print_error('Error loading proposals')
        errmsg = ''.join(traceback.format_exception_only(err[0], err[1]))
        QMessageBox.critical(self, ('Error loading proposals'), (errmsg))

    def refresh_proposals(self):
        self.smartvote_manager.voted_proposals = 0;
        self.selected_voting_option_map = dict()
        self.on_proposal_option_changed()
        layout = self.verticalLayout_6
        for i in reversed(range(layout.count())):
            layout.itemAt(i).widget().setParent(None)

        util.WaitingDialog(self, ('Reloading proposals...'), self.load_proposal_thread, self.on_load_proposal_successful,self.on_load_proposal_error)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    sys.exit(app.exec_())