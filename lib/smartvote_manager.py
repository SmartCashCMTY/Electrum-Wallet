import threading
import requests, json
import base64

from decimal import Decimal
from electrum_smart.util import print_msg, print_stderr, json_encode, json_decode, UserCancelled
from electrum_smart.bitcoin import COIN

URL_HIVE_VOTING_PORTAL = "https://vote.smartcash.cc/api/v1"

class SmartvoteManager(object):
    """Smartvote manager.

    Keeps track of votes and helps with signing address.
    """
    def __init__(self, wallet):
        self.network_event = threading.Event()
        self.wallet = wallet
        self.avaliable_addresses = {}
        self.selected_addresses = {}
        self.proposals = {}
        self.voted_proposals = 0
        self.load()

    def load(self):
        """Load from wallet storage."""
        self.avaliable_addresses = self.get_avaliable_vote_addresses()
        self.selected_addresses = self.get_avaliable_vote_addresses()

    def update_proposals(self):
        url = "{}/VoteProposals/CheckAddresses".format(URL_HIVE_VOTING_PORTAL)
        data = list(self.avaliable_addresses.keys())
        headers = {'Content-type': 'application/json', 'User-Agent': 'Electrum'}
        response = requests.post(url, json=data, headers=headers)

        if response.ok:
            jData = response.json()
            self.proposals = jData.get("result")
            print_msg("[VOTE API] successfully loaded proposals")
        else:
            response.raise_for_status()

    def get_avaliable_vote_addresses(self):
        addresses = self.wallet.get_addresses()
        vote_addresses = {}
        for addr in addresses:
            c, u, x = self.wallet.get_addr_balance(addr)
            if c >= 1 * COIN:
                vote_addresses[addr] = int(c / COIN)
        return vote_addresses

    def add_vote_address(self, addr):
        c, u, x = self.wallet.get_addr_balance(addr)
        self.selected_addresses[addr] = int(c / COIN)

    def remove_vote_address(self, addr):
        del self.selected_addresses[addr]

    def get_voting_power(self):
        return sum(self.selected_addresses.values())

    def add_thousands_spaces(self, a):
        a = int(a)
        return format(a, ',').replace(',', ' ').replace('.', ',')

    def cast_vote(self, proposal_id, vote_type, selected_addresses, password):
        proposal = None
        proposals = self.proposals

        for p in proposals:
            if (p["proposalId"] == proposal_id):
                proposal = p

        votes = []
        for addr in selected_addresses:
            address_vote = {}
            address_vote["smartAddress"] = addr
            address_vote["signature"] = base64.b64encode(self.wallet.sign_message(addr, proposal["url"], password)).decode('ascii')
            address_vote["voteType"] = vote_type.upper()
            votes.append(address_vote)

        url = "{}/VoteProposals/CastVoteList".format(URL_HIVE_VOTING_PORTAL)
        headers = {'Content-type': 'application/json'}

        data = {}
        data['proposalId'] = proposal_id
        data['votes'] = votes

        response = requests.post(url, json=data, headers=headers)

        if (response.ok):
            jData = json.loads(response.content.decode("utf-8"))
            return jData.get('result')
        else:
            response.raise_for_status()
            return False

