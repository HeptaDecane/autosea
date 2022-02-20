import json
from web3 import Web3
from pathlib import Path
from web3.middleware import geth_poa_middleware

BASE_DIR = Path(__file__).resolve().parent

provider = Web3.HTTPProvider('https://polygon-rpc.com')
web3 = Web3(provider)
web3.middleware_onion.inject(geth_poa_middleware, layer=0)

file = open(BASE_DIR / 'openstore.json', 'r')
contract = json.load(file)
abi = contract['abi']
contract_address = Web3.toChecksumAddress('0x2953399124F0cBB46d2CbACD8A89cF0599974963')
openstore = web3.eth.contract(abi=abi, address=contract_address)


def balance_of(address, token_id):
    address = Web3.toChecksumAddress(address)
    token_id = int(token_id)
    balance = openstore.functions.balanceOf(address, token_id).call()
    return balance


if __name__ == '__main__':
    print('web3 connected:', web3.isConnected())
    print('contract:', openstore.functions.name().call())
