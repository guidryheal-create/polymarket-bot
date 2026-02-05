from dotenv import load_dotenv
import os

from py_clob_client.client import ClobClient
from py_clob_client.constants import AMOY

load_dotenv()

POLYGON_PRIVATE_KEY="6d01e41ee42fc6aa2fda393e8c58240c3879dec405edc16f6850205188448f4e"



def main():
    host = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
    key = "6d01e41ee42fc6aa2fda393e8c58240c3879dec405edc16f6850205188448f4e"
    chain_id = 137
    client = ClobClient(host, key=key, chain_id=chain_id)

    print(client.create_api_key())


main()

"""
ApiCreds(api_key='e8b375d6-312b-27bb-f6b2-9bcc740b6ca0', api_secret='ScuCcaHdBnTdHLORi4QDS894OTU0hZ-jh99vjqY2Qm0=', api_passphrase='28724708c76316adc15099b409306ebc81184a917629e672adef1e06495f6c69')
"""