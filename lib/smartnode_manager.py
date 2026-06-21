from collections import namedtuple, OrderedDict
import base64
import threading
from decimal import Decimal

from . import bitcoin
from .blockchain import hash_header
from .smartnode import MasternodeAnnounce, NetworkAddress
from .util import AlreadyHaveAddress, print_error, bfh, print_msg, format_satoshis_plain

BUDGET_FEE_CONFIRMATIONS = 6
BUDGET_FEE_TX = 5 * bitcoin.COIN
# From masternode.h
MASTERNODE_MIN_CONFIRMATIONS = 15
SMARTNODE_COLLATERAL_VALUE = 100000 * bitcoin.COIN

MasternodeConfLine = namedtuple('MasternodeConfLine', ('alias', 'addr',
        'wif', 'txid', 'output_index'))

def parse_masternode_conf(lines):
    """Construct MasternodeConfLine instances from lines of a masternode.conf file."""
    conf_lines = []
    for line in lines:
        # Comment.
        if line.startswith('#'):
            continue

        s = line.split(' ')
        if len(s) < 5:
            continue
        alias = s[0]
        addr_str = s[1]
        masternode_wif = s[2]
        collateral_txid = s[3]
        collateral_output_n = s[4]

        # Validate input.
        try:
            txin_type, key, is_compressed = bitcoin.deserialize_privkey(masternode_wif)
            assert key
        except Exception:
            raise ValueError('Invalid masternode private key of alias "%s"' % alias)

        if len(collateral_txid) != 64:
            raise ValueError('Transaction ID of alias "%s" must be 64 hex characters.' % alias)

        try:
            collateral_output_n = int(collateral_output_n)
        except ValueError:
            raise ValueError('Transaction output index of alias "%s" must be an integer.' % alias)

        conf_lines.append(MasternodeConfLine(alias, addr_str, masternode_wif, collateral_txid, collateral_output_n))
    return conf_lines

class MasternodeManager(object):
    """Smartnode manager.

    Keeps track of smartnodes and helps with signing broadcasts.
    """
    def __init__(self, wallet, config):
        self.network_event = threading.Event()
        self.wallet = wallet
        self.config = config
        # Subscribed smartnode statuses.
        self.masternode_statuses = {}
        self.load()

    def load(self):
        """Load smartnode from wallet storage."""
        masternodes = self.wallet.storage.get('masternodes', {})
        self.masternodes = [MasternodeAnnounce.from_dict(d) for d in masternodes.values()]

    def send_subscriptions(self):
        if not self.wallet.network.is_connected():
            return
        self.subscribe_to_masternodes()

    def subscribe_to_masternodes(self):
        for mn in self.masternodes:
            #if not mn.announced:
            #    continue
            collateral = mn.get_collateral_str()
            if self.masternode_statuses.get(collateral) is None:
                req = ('masternode.subscribe', [collateral])
                self.wallet.network.send([req], self.masternode_subscription_response)

    def subscribe_to_all_masternodes(self):
        if not self.wallet.network.is_connected():
            print_error("Cannot update smartnode status. Wallet not connected")
            return
        for mn in self.masternodes:
            collateral = mn.get_collateral_str()
            req = ('masternode.subscribe', [collateral])
            self.wallet.network.send([req], self.masternode_subscription_response)

    def get_masternode(self, alias):
        """Get the smartnode labelled as alias."""
        for mn in self.masternodes:
            if mn.alias == alias:
                return mn

    def get_masternode_by_hash(self, hash_):
        for mn in self.masternodes:
            if mn.get_hash() == hash_:
                return mn

    def add_masternode(self, mn, save = True):
        """Add a new smartnode."""
        if any(i.alias == mn.alias for i in self.masternodes):
            raise Exception('A smartnode with alias "%s" already exists' % mn.alias)
        self.masternodes.append(mn)
        if save:
            self.save()

    def remove_masternode(self, alias, save = True):
        """Remove the smartnode labelled as alias."""
        mn = self.get_masternode(alias)
        if not mn:
            raise Exception('Nonexistent smartnode')
        # Don't delete the delegate key if another masternode uses it too.
        if not any(i.alias != mn.alias and i.delegate_key == mn.delegate_key for i in self.masternodes):
            self.wallet.delete_masternode_delegate(mn.delegate_key)

        #Unfreeze coin
        freeze_coin = '{}:{}'.format(mn.vin.get('prevout_hash'), mn.vin.get('prevout_n'))
        self.wallet.set_frozen_coin_state([freeze_coin], False)

        self.masternodes.remove(mn)
        if save:
            self.save()

    def populate_masternode_output(self, alias):
        """Attempt to populate the smartnode's data using its output."""
        mn = self.get_masternode(alias)
        if not mn:
            return
        if mn.announced:
            return
        txid = mn.vin.get('prevout_hash')
        prevout_n = mn.vin.get('prevout_n')
        if not txid or prevout_n is None:
            return
        # Return if it already has the information.
        if mn.collateral_key and mn.vin.get('address') and mn.vin.get('value') == SMARTNODE_COLLATERAL_VALUE:
            return

        tx = self.wallet.transactions.get(txid)
        if not tx:
            return
        if len(tx.outputs()) <= prevout_n:
            return
        _, addr, value = tx.outputs()[prevout_n]
        mn.vin['address'] = addr
        mn.vin['value'] = value
        mn.vin['scriptSig'] = ''

        mn.collateral_key = self.wallet.get_public_keys(addr)[0]
        self.save()
        return True

    def get_masternode_collateral_key(self, addr):
        return self.wallet.get_public_keys(addr)[0]

    def get_masternode_outputs(self, domain = None, exclude_frozen = True):
        """Get spendable coins that can be used as smartnode collateral."""
        coins = self.wallet.get_utxos(domain, exclude_frozen,
                                      mature=True, confirmed_only=True)

        coins[:] = [c for c in coins if c.get('value') == SMARTNODE_COLLATERAL_VALUE]

        avaliable_vins = []
        for coin in coins:
            avaliable_vins.append('%s:%d' % (coin.get('prevout_hash'), coin.get('prevout_n', 0xffffffff)))

        used_vins = []
        for mn in self.masternodes:
            used_vins.append('%s:%d' % (mn.vin.get('prevout_hash'), int(mn.vin.get('prevout_n', 0xffffffff))))

        unavaliable_vins = set(avaliable_vins).intersection(used_vins)

        for vin in unavaliable_vins:
            prevout_hash, prevout_n = vin.split(':')
            [coins.remove(c) for c in coins if (c.get('prevout_hash') == prevout_hash) and (c.get('prevout_n') == int(prevout_n))]

        return coins

    def get_masternode_outputs_old(self, domain = None, exclude_frozen = True):
        """Get spendable coins that can be used as smartnode collateral."""
        coins = self.wallet.get_utxos(domain, exclude_frozen,
                                      mature=True, confirmed_only=True)

        used_vins = map(lambda mn: '%s:%d' % (mn.vin.get('prevout_hash'), mn.vin.get('prevout_n', 0xffffffff)), self.masternodes)
        unused = lambda d: '%s:%d' % (d['prevout_hash'], d['prevout_n']) not in used_vins

        #smartnode output
        correct_amount = lambda d: d['value'] == SMARTNODE_COLLATERAL_VALUE

        # Valid outputs have a value of exactly SMARTNODE_COLLATERAL_VALUE SMART and
        # are not in use by an existing smartnode.
        is_valid = lambda d: correct_amount(d) and unused(d)

        coins = filter(is_valid, coins)
        return coins

    def get_delegate_privkey(self, pubkey):
        """Return the private delegate key for pubkey (if we have it)."""
        return self.wallet.get_delegate_private_key(pubkey)

    def check_can_sign_masternode(self, alias):
        """Raise an exception if alias can't be signed and announced to the network."""
        mn = self.get_masternode(alias)
        if not mn:
            raise Exception('Nonexistent smartnode')
        if not mn.vin.get('prevout_hash'):
            raise Exception('Collateral TxId is not specified')
        if not mn.collateral_key:
            raise Exception('Could not allocate outpoint. Collateral TxId is not specified')
        if not mn.delegate_key:
            raise Exception('Smartnode delegate key is not specified')
        if not mn.addr.ip:
            raise Exception('Smartnode has no IP address')

        # Ensure that the collateral payment has >= MASTERNODE_MIN_CONFIRMATIONS.
        height, conf, timestamp = self.wallet.get_tx_height(mn.vin['prevout_hash'])
        if conf < MASTERNODE_MIN_CONFIRMATIONS:
            raise Exception('Collateral payment must have at least %d confirmations (current: %d)' % (MASTERNODE_MIN_CONFIRMATIONS, conf))
        # Ensure that the Smartnode's vin is valid.
        if mn.vin.get('value', 0) != SMARTNODE_COLLATERAL_VALUE:
            raise Exception('Smartnode requires a collateral {} SMART output.'.format(format_satoshis_plain(SMARTNODE_COLLATERAL_VALUE)))

        # Ensure collateral was not moved or spent.
        uxto = '{}:{}'.format(mn.vin['prevout_hash'], mn.vin['prevout_n'])
        utxos = self.wallet.get_addr_utxo(mn.vin['address'])
        if uxto not in utxos:
            raise Exception('Smartnode requires a {} SMART collateral. Check if funds have been moved or spent.'.format(format_satoshis_plain(SMARTNODE_COLLATERAL_VALUE)))


    def check_masternode_status(self, alias):
        """Raise an exception if alias can't be signed and announced to the network."""
        mn = self.get_masternode(alias)
        if not mn:
            raise Exception('Nonexistent smartnode')
        if not mn.vin.get('prevout_hash'):
            raise Exception('Collateral payment is not specified')
        if not mn.collateral_key:
            raise Exception('Collateral key is not specified')
        if not mn.delegate_key:
            raise Exception('Smartnode delegate key is not specified')
        if not mn.addr.ip:
            raise Exception('Smartnode has no IP address')

        # Ensure that the collateral payment has >= MASTERNODE_MIN_CONFIRMATIONS.
        height, conf, timestamp = self.wallet.get_tx_height(mn.vin['prevout_hash'])
        if conf < MASTERNODE_MIN_CONFIRMATIONS:
            raise Exception('Collateral payment must have at least %d confirmations (current: %d)' % (MASTERNODE_MIN_CONFIRMATIONS, conf))
        # Ensure that the Smartnode's vin is valid.
        if mn.vin.get('value', 0) != SMARTNODE_COLLATERAL_VALUE:
            raise Exception('Smartnode requires a collateral {} SMART output.'.format(format_satoshis_plain(SMARTNODE_COLLATERAL_VALUE)))

        collat = mn.get_collateral_str()
        status = self.masternode_statuses.get(collat)

        return status

    def save(self):
        """Save smartnodes."""
        masternodes = {}
        for mn in self.masternodes:
            masternodes[mn.alias] = mn.dump()

        self.wallet.storage.put('masternodes', masternodes)

    def sign_announce(self, alias, password):
        """Sign a Smartnode Announce message for alias."""
        self.check_can_sign_masternode(alias)
        mn = self.get_masternode(alias)
        # Ensure that the smartnode's vin is valid.
        if mn.vin.get('scriptSig') is None:
            mn.vin['scriptSig'] = ''
        if mn.vin.get('sequence') is None:
            mn.vin['sequence'] = 0xffffffff
        # Ensure that the smartnode's last_ping is current
        height = self.wallet.get_local_height() - 33  # 33 * 55s => 30min
        blockchain = self.wallet.network.blockchain()
        header = blockchain.read_header(height)
        mn.last_ping.block_hash = hash_header(header)
        mn.last_ping.vin = mn.vin

        # Sign ping with delegate key.
        self.wallet.sign_masternode_ping(mn.last_ping, mn.delegate_key)

        # After creating the Smartnode Ping, sign the Smartnode Announce.
        address = bitcoin.public_key_to_p2pkh(bfh(mn.collateral_key))
        mn.sig = self.wallet.sign_message(address, mn.serialize_for_sig(update_time=True), password)

        return mn

    def send_announce(self, alias):
        """Broadcast a Smartnode Announce message for alias to the network.

        Returns a 2-tuple of (error_message, was_announced).
        """
        if not self.wallet.network.is_connected():
            raise Exception('Not connected')

        mn = self.get_masternode(alias)
        # Vector-serialize the smartnode.
        serialized = '01' + mn.serialize()
        errmsg = []
        callback = lambda r: self.broadcast_announce_callback(alias, errmsg, r)
        self.network_event.clear()
        self.wallet.network.send([('masternode.announce.broadcast', [serialized])], callback)
        self.network_event.wait()
        self.subscribe_to_masternodes()
        if errmsg:
            errmsg = errmsg[0]
        return (errmsg, mn.announced)

    def get_broadcast_message(self, alias, password):

        if not self.wallet.network.is_connected():
            raise Exception('Not connected')

        self.sign_announce(alias, password)
        mn = self.get_masternode(alias)
        serialized = '01' + mn.serialize()
        return serialized

    def broadcast_announce_callback(self, alias, errmsg, r):
        """Callback for when a Smartnode Announce message is broadcasted."""
        try:
            self.on_broadcast_announce(alias, r)
        except Exception as e:
            errmsg.append(str(e))
        finally:
            self.save()
            self.network_event.set()

    def on_broadcast_announce(self, alias, r):
        """Validate the server response."""
        err = r.get('error')
        if err:
            raise Exception('Error response: %s' % str(err))

        result = r.get('result')

        mn = self.get_masternode(alias)
        mn_hash = mn.get_hash()
        mn_dict = result.get(mn_hash)
        if not mn_dict:
            raise Exception('No result for expected Smartnode Hash. Got %s' % result)

        if mn_dict.get('errorMessage'):
            raise Exception('Announce was rejected: %s' % mn_dict['errorMessage'])
        if mn_dict.get(mn_hash) != 'successful':
            raise Exception('Announce was rejected (no error message specified)')

        mn.announced = True

    def import_masternode_delegate(self, sec):
        """Import a WIF delegate key.

        An exception will not be raised if the key is already imported.
        """
        try:
            pubkey = self.wallet.import_masternode_delegate(sec)
        except AlreadyHaveAddress:
            txin_type, key, is_compressed = bitcoin.deserialize_privkey(sec)
            pubkey = bitcoin.public_key_from_private_key(key, is_compressed)
        return pubkey

    def import_masternode_conf_lines(self, conf_lines, password):
        """Import a list of SmartnodeConfLine."""
        def already_have(line):
            for masternode in self.masternodes:
                # Don't let aliases collide.
                if masternode.alias == line.alias:
                    return True
                # Don't let outputs collide.
                if masternode.vin.get('prevout_hash') == line.txid and masternode.vin.get('prevout_n') == line.output_index:
                    return True
            return False

        num_imported = 0
        for conf_line in conf_lines:
            if already_have(conf_line):
                continue
            # Import delegate WIF key for signing last_ping.
            public_key = self.import_masternode_delegate(conf_line.wif)

            addr = conf_line.addr.split(':')
            addr = NetworkAddress(ip=addr[0], port=int(addr[1]))
            vin = {'prevout_hash': conf_line.txid, 'prevout_n': conf_line.output_index}
            mn = MasternodeAnnounce(alias=conf_line.alias, vin=vin,  
                    delegate_key = public_key, addr=addr)
            self.add_masternode(mn)
            try:
                self.populate_masternode_output(mn.alias)
            except Exception as e:
                print_error(str(e))
            num_imported += 1

        return num_imported

    def masternode_subscription_response(self, response):
        """Callback for when a masternode's status changes."""
        collateral = response['params'][0]
        mn = None
        for masternode in self.masternodes:
            if masternode.get_collateral_str() == collateral:
                mn = masternode
                break

        if not mn:
            return

        if not 'result' in response:
            return

        status = response['result']
        if status is None:
            status = False
        print_msg('Received updated status for smartnode %s: "%s"' % (mn.alias, status))
        self.masternode_statuses[collateral] = status