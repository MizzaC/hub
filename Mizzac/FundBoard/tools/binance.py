from binance.client import Client
import pandas as pd
import time

class Binance:


    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = Client(api_key, api_secret)

    def get_deposit_history(self):
        return self.client.get_deposit_history()

    def get_withdraw_history(self):
        return self.client.get_withdraw_history()

    def get_trade_history(self):
        trades = []
        for symbol_data in self.client.get_all_tickers():
            symbol = symbol_data['symbol']
            from_id = None
            while True:
                part = self.client.get_my_trades(symbol=symbol, fromId=from_id, limit=500)
                if not part:
                    break
                trades.extend(part)
                if len(part) < 500:
                    break
                from_id = part[-1]['id'] + 1
                time.sleep(0.2)
        return trades

    def format_history(deposits, withdrawals, trades):
        df_deposits = pd.DataFrame(deposits)
        df_deposits['Operation'] = 'Deposit'
        if not df_deposits.empty:
            df_deposits['UTC_Time'] = pd.to_datetime(df_deposits['insertTime'], unit='ms')

        df_withdrawals = pd.DataFrame(withdrawals)
        df_withdrawals['Operation'] = 'Withdrawal'
        if not df_withdrawals.empty:
            df_withdrawals['UTC_Time'] = pd.to_datetime(df_withdrawals['insertTime'], unit='ms')

        df_trades = pd.DataFrame(trades)
        df_trades['Operation'] = 'Trade'
        if not df_trades.empty:
            df_trades['UTC_Time'] = pd.to_datetime(df_trades['time'], unit='ms')

        df_combined = pd.concat([df_deposits, df_withdrawals, df_trades], ignore_index=True, sort=False)
        return df_combined

    # Exemple d'exécution
    deposits = get_deposit_history()['depositList']
    withdrawals = get_withdraw_history()['withdrawList']
    trades = get_trade_history()

    df = format_history(deposits, withdrawals, trades)
    print(df.head())
