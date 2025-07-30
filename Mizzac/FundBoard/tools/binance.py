import time
import os
from dotenv import load_dotenv
import hmac
import hashlib
import requests
from urllib.parse import urlencode

class Binance_Reader:
    """
    Classe pour interagir avec l'API Binance.
    Uniquement valable pour le moment pour la lecture, l'écriture (passage d'ordres) recommande une clé API assymétrique et l'utilisation de de la v4.
    """

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_API_SECRET')
        self.Request_Weight_Limit = {'X-SAPI-USED-UID-WEIGHT-1M': 180000, 'X-SAPI-USED-IP-WEIGHT-1M': 12000, 'x-mbx-used-weight-1m': 6000}
        self.Current_Weight = {'X-SAPI-USED-UID-WEIGHT-1M': 0, 'X-SAPI-USED-IP-WEIGHT-1M': 0, 'x-mbx-used-weight-1m': 0}
        self.Request_Weight_Value = {'/sapi/v1/convert/tradeFlow' : {'Weight': 3000, 'Based_Weight': 'X-SAPI-USED-UID-WEIGHT-1M'},
                                     '/sapi/v1/convert/exchangeInfo' : {'Weight': 3000, 'Based_Weight': 'X-SAPI-USED-IP-WEIGHT-1M'},
                                     '/sapi/v1/convert/assetInfo' : {'Weight': 100, 'Based_Weight': 'X-SAPI-USED-IP-WEIGHT-1M'},
                                     '/sapi/v1/convert/orderStatus' : {'Weight': 100, 'Based_Weight': 'X-SAPI-USED-UID-WEIGHT-1M'},
                                     '/sapi/v1/fiat/payments' : {'Weight': 1, 'Based_Weight': 'X-SAPI-USED-IP-WEIGHT-1M'},
                                     '/sapi/v1/fiat/orders' : {'Weight': 90000, 'Based_Weight': 'X-SAPI-USED-UID-WEIGHT-1M'},
                                    }
        
        
        
        
        


    def binance_request(self, endpoint, params=None, signed=True, OptionnalAuth=False, base_url="https://api.binance.com"):
        """
        Envoie une requête vers l'API Binance.
        
        :param http_method: "GET", "POST", "DELETE", "PUT"
        :param endpoint: ex: "/api/v3/account" ou "/sapi/v1/convert/tradeFlow"
        :param params: dictionnaire de paramètres à envoyer
        :param api_key: ta clé API publique (nécessaire si signed=True)
        :param api_secret: ta clé API secrète (nécessaire si signed=True)
        :param signed: booléen – true si signature requise
        :param base_url: URL de base (ex: testnet ou spot)
        :return: objet `requests.Response`
        """
        
        if params is None:
            params = {}

        headers = {}
        if signed:
            params['timestamp'] = int(time.time() * 1000)
            query_string = urlencode(params)
            signature = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
            params['signature'] = signature
            headers['X-MBX-APIKEY'] = self.api_key
        elif OptionnalAuth:
            headers['X-MBX-APIKEY'] = self.api_key  # Pour certains endpoints publics avec auth optionnelle

        url = f"{base_url}{endpoint}"

        response = requests.get(url, headers=headers, params=params)

        response_payload = response.json()
        response_headers = response.headers
        response_status_code = response.status_code
        
        if response_status_code == 429:
            time.sleep(60)
        elif response_status_code == 418:
            time.sleep( response_headers.get('Retry-After', 120) )

        return response_payload, response_headers, response_status_code

    # def get_deposit_history(self):
    #     return self.client.get_deposit_history()

    # def get_withdraw_history(self):
    #     return self.client.get_withdraw_history()

    # def get_trade_history(self):
    #     trades = []
    #     for symbol_data in self.client.get_all_tickers():
    #         symbol = symbol_data['symbol']
    #         from_id = None
    #         while True:
    #             part = self.client.get_my_trades(symbol=symbol, fromId=from_id, limit=500)
    #             if not part:
    #                 break
    #             trades.extend(part)
    #             if len(part) < 500:
    #                 break
    #             from_id = part[-1]['id'] + 1
    #             time.sleep(0.2)
    #     return trades

    # def format_history(deposits, withdrawals, trades):
    #     df_deposits = pd.DataFrame(deposits)
    #     df_deposits['Operation'] = 'Deposit'
    #     if not df_deposits.empty:
    #         df_deposits['UTC_Time'] = pd.to_datetime(df_deposits['insertTime'], unit='ms')

    #     df_withdrawals = pd.DataFrame(withdrawals)
    #     df_withdrawals['Operation'] = 'Withdrawal'
    #     if not df_withdrawals.empty:
    #         df_withdrawals['UTC_Time'] = pd.to_datetime(df_withdrawals['insertTime'], unit='ms')

    #     df_trades = pd.DataFrame(trades)
    #     df_trades['Operation'] = 'Trade'
    #     if not df_trades.empty:
    #         df_trades['UTC_Time'] = pd.to_datetime(df_trades['time'], unit='ms')

    #     df_combined = pd.concat([df_deposits, df_withdrawals, df_trades], ignore_index=True, sort=False)
    #     return df_combined

    # Exemple d'exécution

