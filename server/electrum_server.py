#!/usr/bin/env python3
"""Electrum Server for SmartCash 3.0.0 - with Merkle proofs."""

import asyncio, json, logging, urllib.request, base64, ssl as ssllib, hashlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("electrum")

RPC_URL = "http://151.252.59.32:29679/"
RPC_USER = "smartcashrpc"
RPC_PASS = "a551f91d9199429fa89e7b39cbdce00412221b56de0384211e16a9da614354ab"
TCP_PORT = 50001
SSL_PORT = 50002
CERTFILE = "/etc/electrumx/server.crt"
KEYFILE = "/etc/electrumx/server.key"
REST_MAX = 2000

executor = ThreadPoolExecutor(max_workers=16)
subscriptions = defaultdict(set)
HEADER_CACHE = {}

ADDRESS_MAP = {"9919e6f3074e7db31a14c0f811a345b9b553303be48f522870a05d813f4209de": "SQjUwjG7FtvGrW5keDckwum5j34UBTbWuM"}

def rpc_sync(method, params=[]):
    data = json.dumps({"method": method, "params": params})
    auth = base64.b64encode(f"{RPC_USER}:{RPC_PASS}".encode()).decode()
    req = urllib.request.Request(RPC_URL, data=data.encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("error"):
                raise Exception(str(result["error"]))
            return result["result"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            err = json.loads(body)
            msg = err.get("error", {}).get("message", str(e))
        except:
            msg = body[:200] if body else str(e)
        raise Exception(msg)

def rpc_rest_sync(path):
    auth = base64.b64encode(f"{RPC_USER}:{RPC_PASS}".encode()).decode()
    req = urllib.request.Request(f"{RPC_URL}rest/{path}")
    req.add_header("Authorization", f"Basic {auth}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().hex()

async def rpc(method, params=[]):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, rpc_sync, method, params)

def parse_header_hex(hh):
    if len(hh) < 160:
        return {"hex": hh, "block_height": 0, "version": 1, "prev_block_hash": "00"*32, "merkle_root": "00"*32, "timestamp": 0, "bits": 0, "nonce": 0}
    s = bytes.fromhex(hh[:160])
    return {"hex": hh, "version": int.from_bytes(s[0:4], "little"), "prev_block_hash": s[4:36][::-1].hex(), "merkle_root": s[36:68][::-1].hex(), "timestamp": int.from_bytes(s[68:72], "little"), "bits": int.from_bytes(s[72:76], "little"), "nonce": int.from_bytes(s[76:80], "little")}

async def get_header(height):
    if height in HEADER_CACHE:
        return HEADER_CACHE[height]
    loop = asyncio.get_event_loop()
    bh = await loop.run_in_executor(executor, rpc_sync, "getblockhash", [height])
    hh = await loop.run_in_executor(executor, rpc_sync, "getblockheader", [bh, False])
    HEADER_CACHE[height] = hh
    return hh

def get_headers_batch(start_height, count):
    try:
        bh = rpc_sync("getblockhash", [start_height])
        h = rpc_sync("getblockcount")
        actual = min(count, h + 1 - start_height)
        first = min(actual, REST_MAX)
        result = rpc_rest_sync(f"headers/{first}/{bh}.bin")
        if actual > REST_MAX:
            bh2 = rpc_sync("getblockhash", [start_height + REST_MAX])
            result += rpc_rest_sync(f"headers/{actual - REST_MAX}/{bh2}.bin")
        return result
    except Exception as e:
        log.error(f"REST batch failed at {start_height}: {e}")
        return ""

def compute_merkle_branch(txid, height):
    try:
        bh = rpc_sync("getblockhash", [height])
        raw_hex = rpc_rest_sync(f"block/{bh}.bin")
        raw_block = bytes.fromhex(raw_hex)
        pos = 80
        def read_cs(data, pos):
            v = data[pos]; pos += 1
            if v < 253: return v, pos
            if v == 253: return int.from_bytes(data[pos:pos+2], "little"), pos+2
            if v == 254: return int.from_bytes(data[pos:pos+4], "little"), pos+4
            return int.from_bytes(data[pos:pos+8], "little"), pos+8
        tx_count, pos = read_cs(raw_block, pos)
        tx_hashes = []
        for i in range(tx_count):
            start = pos
            pos += 4
            vin, pos = read_cs(raw_block, pos)
            for j in range(vin):
                pos += 36
                ss, pos = read_cs(raw_block, pos)
                pos += ss + 4
            vout, pos = read_cs(raw_block, pos)
            for j in range(vout):
                pos += 8
                ss, pos = read_cs(raw_block, pos)
                pos += ss
            pos += 4
            h = hashlib.sha256(hashlib.sha256(raw_block[start:pos]).digest()).digest()
            tx_hashes.append(h)
        target_hash = bytes.fromhex(txid)[::-1]
        target_pos = None
        for i, h in enumerate(tx_hashes):
            if h == target_hash:
                target_pos = i
                break
        if target_pos is None:
            return None
        branch = []
        idx = target_pos
        hashes = tx_hashes[:]
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                h = hashlib.sha256(hashlib.sha256(combined).digest()).digest()
                new_hashes.append(h)
                if i == (idx & ~1):
                    sibling = hashes[i+1] if idx & 1 else hashes[i]
                    branch.append(sibling[::-1].hex())
            hashes = new_hashes
            idx //= 2
        return {"block_height": height, "merkle": branch, "pos": target_pos}
    except Exception as e:
        log.error(f"Merkle error {txid}/{height}: {e}")
        return None

async def handle_client(reader, writer):
    try:
        buf = b""
        while True:
            chunk = await reader.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    req = json.loads(line)
                    method = req.get("method", "?")
                    log.info(f"REQ {method} {str(req.get('params',[]))[:80]}")
                    result = await process_request(req)
                    if result is not None:
                        writer.write(json.dumps(result).encode() + b"\n")
                        await writer.drain()
                    else:
                        writer.write(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": None}).encode() + b"\n")
                        await writer.drain()
                except json.JSONDecodeError:
                    pass
    except:
        pass
    finally:
        writer.close()

async def process_request(req):
    method = req.get("method", "")
    params = req.get("params", [])
    mid = req.get("id")
    try:
        result = None
        if method == "server.version":
            result = ["Electrum-SMART 3.0.0", "1.2"]
        elif method == "server.banner":
            h = await rpc("getblockcount")
            result = f"SmartCash 3.0.0 - Height: {h}"
        elif method == "server.peers.subscribe":
            result = []
        elif method == "server.features":
            result = {"genesis_hash": "000007acc6970b812948d14ea5a0a13db0fdd07d5047c7e69101fa8b361e05a4", "protocol_max": "1.2", "protocol_min": "1.0", "pruning": None, "server_version": "Electrum-SMART 3.0.0"}
        elif method == "blockchain.headers.subscribe":
            height = await rpc("getblockcount")
            hh = await get_header(height)
            parsed = parse_header_hex(hh)
            parsed["block_height"] = height
            result = parsed
        elif method in ("blockchain.block.get_header", "blockchain.block.header"):
            hh = await get_header(params[0])
            result = parse_header_hex(hh)
            result["block_height"] = params[0]
        elif method == "blockchain.block.get_chunk":
            idx = params[0]
            sh = idx * 2016
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, get_headers_batch, sh, 2016)
        elif method == "blockchain.transaction.get_merkle":
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(executor, compute_merkle_branch, params[0], params[1])
        elif method == "blockchain.transaction.broadcast":
            tx_hex = params[0]
            try:
                txid = await rpc("sendrawtransaction", [tx_hex])
                result = txid
            except Exception as e:
                err_msg = str(e)
                log.error(f"Broadcast error: {err_msg}")
                result = "error: " + err_msg
        elif method == "blockchain.transaction.get":
            try:
                result = await rpc("getrawtransaction", [params[0]])
            except:
                result = None
        elif method == "blockchain.estimatefee":
            result = 0.001
        elif method == "blockchain.relayfee":
            result = 0.00001
        elif method.startswith("blockchain.scripthash.subscribe"):
            sh = params[0] if params else ""
            addr = ADDRESS_MAP.get(sh)
            if addr:
                try:
                    txs = await rpc("getaddressdeltas", [{"addresses": [addr]}])
                    seen = set()
                    history = []
                    for d in txs:
                        txid = d["txid"]
                        if txid not in seen:
                            seen.add(txid)
                            history.append({"tx_hash": txid, "height": d.get("height", 0)})
                    status_str = "".join(f"{item['tx_hash']}:{item['height']}:" for item in history)
                    result = hashlib.sha256(status_str.encode()).hexdigest()
                except Exception as e:
                    log.error(f"SUB ERR: {e}")
                    result = None
            else:
                result = None
        elif method.startswith("blockchain.scripthash.get_history"):
            sh = params[0] if params else ""
            addr = ADDRESS_MAP.get(sh)
            if addr:
                try:
                    txs = await rpc("getaddressdeltas", [{"addresses": [addr]}])
                    seen = set()
                    result = []
                    for d in txs:
                        txid = d["txid"]
                        if txid not in seen:
                            seen.add(txid)
                            result.append({"tx_hash": txid, "height": d.get("height", 0)})
                except:
                    result = []
            else:
                result = []
        elif method.startswith("blockchain.scripthash.get_balance"):
            sh = params[0] if params else ""
            addr = ADDRESS_MAP.get(sh)
            if addr:
                try:
                    bal = await rpc("getaddressbalance", [{"addresses": [addr]}])
                    result = {"confirmed": str(bal.get("balance", 0)), "unconfirmed": "0"}
                except:
                    result = {"confirmed": "0", "unconfirmed": "0"}
            else:
                result = {"confirmed": "0", "unconfirmed": "0"}
        elif method.startswith("blockchain.address.get_history"):
            addr = params[0] if params else ""
            try:
                txs = await rpc("getaddressdeltas", [{"addresses": [addr]}])
                seen = set()
                result = []
                for d in txs:
                    txid = d["txid"]
                    if txid not in seen:
                        seen.add(txid)
                        result.append({"tx_hash": txid, "height": d.get("height", 0)})
            except:
                result = []
        elif method.startswith("blockchain.address.get_balance"):
            result = {"confirmed": "0", "unconfirmed": "0"}
        elif method.startswith("server.donation_address"):
            result = ""
        elif method.startswith("server.ping"):
            result = None
        elif method.startswith("smartrewards.current"):
            result = {}
        elif method.startswith("smartrewards.check"):
            result = {}
        elif method.startswith("smartrewards"):
            result = None
    except Exception as e:
        log.error(f"ERR {method}: {e}")
        result = None
    return {"jsonrpc": "2.0", "id": mid, "result": result}

async def main():
    try:
        h = rpc_sync("getblockcount")
        log.info(f"Daemon height: {h}")
    except Exception as e:
        log.error(f"Daemon error: {e}")
    ssl_ctx = None
    try:
        ssl_ctx = ssllib.create_default_context(ssllib.Purpose.CLIENT_AUTH)
        ssl_ctx.load_cert_chain(CERTFILE, KEYFILE)
    except:
        pass
    tcp = await asyncio.start_server(handle_client, "0.0.0.0", TCP_PORT)
    ssl_srv = await asyncio.start_server(handle_client, "0.0.0.0", SSL_PORT, ssl=ssl_ctx) if ssl_ctx else None
    log.info(f"Listening TCP:{TCP_PORT} SSL:{SSL_PORT}")
    async with tcp:
        await tcp.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())
