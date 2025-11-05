#!/usr/bin/env python
# coding: utf-8

import json
import os
import oandapyV20
import oandapyV20.endpoints.positions as oanda_positions_api
import oandapyV20.endpoints.accounts as oanda_accounts_api
from hammer_shooting_star.hammer_shooting_star import HammerShootingStar
from patterns.patterns import Patterns
from rsi_strategy.rsi_strategy import RSIStrategy
from support_resistance.support_resistance_v1 import SupportResistanceV1
from trader.trader import Trader
from svm_strategy.svm_strategy import SVMStrategy
from marsi_strategy.marsi_strategy import MARSIStrategy
import request_historical_data.request_historical_data as rhd
import request_historical_data.callback as rhd_callback
import pandas as pd
import time
from collections import defaultdict
from ib_api_client.ib_api_client import IBApiClient
from ibapi.contract import Contract
import matplotlib.pyplot as plt
from plot.plot import Plot
from support_resistance.support_resistance import SupportResistance

import threading
import collections

from technical_indicators.technical_indicators import TechnicalIndicators
from machine_learning.svm_model_trainer import SVMModelTrainer
from machine_learning.lstm_model_trainer import LSTMModelTrainer

from dotenv import load_dotenv
import os

load_dotenv(".env")


# matplotlib.use("MacOSX")
plt.style.use("fivethirtyeight")


def run_loop():
    client.run()


oanda_positions_queue = []
oanda_account_summary_queue = []


def updateOpenPosition():
    while True:
        accountID = os.environ.get("OANDA_ACCOUNT_ID")
        client = oandapyV20.API(
            access_token=os.environ.get("OANDA_ACCESS_TOKEN")
        )  # , environment="live"
        r = oanda_positions_api.OpenPositions(accountID=accountID)
        client.request(r)
        oanda_positions_queue.pop() if len(oanda_positions_queue) > 0 else None
        oanda_positions = {}
        positions = r.response["positions"]
        for position in positions:
            instrument = position["instrument"]
            oanda_positions[instrument] = position
        oanda_positions_queue.append(oanda_positions)
        # print(oanda_positions_queue)
        time.sleep(10)


def updateAccountSummary():
    while True:
        accountID = os.environ.get("OANDA_ACCOUNT_ID")
        client = oandapyV20.API(
            access_token=os.environ.get("OANDA_ACCESS_TOKEN")
        )  # , environment="live"

        r = oanda_accounts_api.AccountSummary(accountID)
        client.request(r)
        oanda_account_summary_queue.pop() if len(
            oanda_account_summary_queue
        ) > 0 else None
        oanda_account_summary = r.response["account"]
        oanda_account_summary_queue.append(oanda_account_summary)
        # print(oanda_account_summary_queue)
        time.sleep(10)

plots_queue = collections.deque([])
oanda_client = oandapyV20.API(
    access_token=os.environ.get("OANDA_ACCESS_TOKEN")
)  # , environment='live'

if __name__ == "__main__":

    callbackFnMap = defaultdict(lambda: defaultdict(lambda: None))
    contextMap = defaultdict(lambda: defaultdict(lambda: None))
    client = IBApiClient(callbackFnMap, contextMap)
    client.connect('127.0.0.1', 7497, 123)

    # Start the socket in a thread
    api_thread = threading.Thread(target=run_loop, daemon=True)
    api_thread.start()

    oanda_positions_thread = threading.Thread(target=updateOpenPosition, daemon=True)
    oanda_positions_thread.start()
    oanda_account_thread = threading.Thread(target=updateAccountSummary, daemon=True)
    oanda_account_thread.start()

    time.sleep(1)  # Sleep interval to allow time for connection to server

    while True:
        if isinstance(client.nextorderId, int):
            print("connected")
            break
        else:
            print("Waiting for connection to server")
            time.sleep(1)

    ########################### REQUEST MARKED DATA #################################
    # app.reqMarketDataType(MarketDataTypeEnum.REALTIME)
    # app.reqMarketDataType(MarketDataTypeEnum.DELAYED)

    # id = 1000
    # contract = Contract()
    # contract.symbol = 'EUR'
    # contract.secType = 'CASH'
    # contract.exchange = 'IDEALPRO'
    # contract.currency = 'USD'

    # from request_market_data.request_market_data import RequestMarketData
    # from request_market_data.callback import Callback as RMDCallback
    # rmd_object = RequestMarketData(app, callbackFnMap)
    # rmd_cb = RMDCallback(askPriceMap, bidPriceMap)
    # rmd_object.request_market_data(
    #     enel_id, enel_contract, rmd_cb.handleMktDataEnel)
    # rmd_object.request_market_data(id, contract, , handleDataAlibaba)
    # request_market_data.request_markeczt_data(bitcoin_futures_id, bitcoin_futures_contract, handleDataBitcoinFutures)
    # request_market_data.request_market_data(eur_usd_id, eur_usd_contract, handleDataEurUsd)
    ########################### REQUEST MARKED DATA #################################

    def process_contract_data(df, technical_indicators, file_to_save, contract):
        df = technical_indicators.execute(df)
        # _ = RSIStrategy().execute(df)
        # printStrategyMarkersFn = HammerShootingStar().execute(df)
        marsiStrategyMarkersFn = MARSIStrategy().execute(df)
        srv1 = SupportResistanceV1(plots_queue, file_to_save)
        srv1MarkersFn, y_lines = srv1.execute(df)
        # SupportResistance(candlestick_data, plots_queue, file_to_save).process_data_with_file(df)
        Plot(df, plots_queue, contract).plot(marsiStrategyMarkersFn, srv1MarkersFn)
        # LSTMModelTrainer(plots_queue, file_to_save).process_data(df)

        # df, model = SVMModelTrainer(
        #     plots_queue, file_to_save).process_data_with_file(df)

        # Request new historical data in "live" mode so that actions can be taken on the market
        # strategy = SVMStrategy(df, model, file_to_save,
        #                        client, contract, trader)
        # The historical data from this call will be simply ignored. We are using it just to get the updates and apply the strategy on them.
        # client.nextorderId += 1
        # rhd_object.request_historical_data(
        #     reqID=client.nextorderId, contract=contract, interval="1 D", timePeriod="15 mins", dataType='MIDPOINT', rth=0, timeFormat=2, keepUpToDate=True, atDatapointFn=lambda x, y: None, afterAllDataFn=lambda reqId, start, end: print("Do nothing", reqId, start, end), atDatapointUpdateFn=strategy.executeTrade)

    ########################### REQUEST HISTORICAL DATA #################################
    with open("contracts.json") as f:
        data = json.load(f)
        print(data)
        id = client.nextorderId
        for _contract in data["contracts"]:
            candlestick_data = []
            contract = Contract()
            fields = str.split(_contract, ",")
            print(fields)
            contract.symbol = fields[0]
            contract.currency = fields[1]
            contract.secType = fields[2]
            contract.exchange = fields[3]
            rhd_object = rhd.RequestHistoricalData(client, callbackFnMap, contextMap)
            rhd_cb = rhd_callback.Callback(candlestick_data)
            interval = "6 M"
            timePeriod = "1 hour"
            file_to_save = "data/data-{}-{}-{}-{}-{}-{}.csv".format(
                contract.symbol,
                contract.secType,
                contract.exchange,
                contract.currency,
                interval,
                timePeriod,
            )
            technical_indicators = TechnicalIndicators(candlestick_data, file_to_save)
            # budget = 5_000
            # trader = Trader(
            #     ibkr_client=client,
            #     oanda_client=oanda_client,
            #     oanda_positions=oanda_positions_queue,
            #     oanda_account_summary=oanda_positions_queue,
            #     callbackFnMap=callbackFnMap,
            #     budget=budget,
            # )
            print("Processing contract: ", contract)
            if not os.path.exists(file_to_save):
                rhd_object.request_historical_data(
                    reqID=id, contract=contract, interval=interval, timePeriod=timePeriod, dataType='MIDPOINT', rth=0, timeFormat=2, keepUpToDate=False, atDatapointFn=rhd_cb.handle, afterAllDataFn=process_contract_data, atDatapointUpdateFn=lambda x, y: None, technicalIndicators=technical_indicators, fileToSave=file_to_save, candlestickData=candlestick_data)
                id += 1
            else:
                print("File already exists. Loading data from CSV")
                df = pd.read_csv(file_to_save, index_col=[0])
                process_contract_data(df, technical_indicators, file_to_save, contract)
    ########################### REQUEST HISTORICAL DATA #################################

    while True:
        # manage plots
        if len(plots_queue) > 0:
            seriesFn = plots_queue.pop()
            seriesFn()
        else:
            time.sleep(2)
