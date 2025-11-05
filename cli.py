#!/usr/bin/env python3
import argparse
import os
import json
import threading
import collections
import time

import pandas as pd

from ib_api_client.ib_api_client import IBApiClient
from ibapi.contract import Contract

import request_historical_data.request_historical_data as rhd
import request_historical_data.callback as rhd_callback

from technical_indicators.technical_indicators import TechnicalIndicators
from plot.plot import Plot
from marsi_strategy.marsi_strategy import MARSIStrategy
from support_resistance.support_resistance_v1 import SupportResistanceV1

# Note: ML trainers are imported lazily inside their commands to avoid
# forcing TensorFlow/Keras dependencies when not needed.


def _connect_ib():
    callbackFnMap = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
    contextMap = collections.defaultdict(lambda: collections.defaultdict(lambda: None))
    client = IBApiClient(callbackFnMap, contextMap)
    client.connect('127.0.0.1', 7497, 123)

    def run_loop():
        client.run()

    api_thread = threading.Thread(target=run_loop, daemon=True)
    api_thread.start()

    for _ in range(60):
        if isinstance(getattr(client, 'nextorderId', None), int):
            return client, callbackFnMap, contextMap
        time.sleep(1)
    raise RuntimeError("Could not connect to IB within 60s")


def cmd_fetch_process_plot(args: argparse.Namespace):
    client, callbackFnMap, contextMap = _connect_ib()

    with open("contracts.json") as f:
        data = json.load(f)

    plots_queue = []
    id_counter = client.nextorderId

    def process_contract_data(df, technical_indicators, file_to_save, contract):
        df = technical_indicators.execute(df)
        marsiStrategyMarkersFn = MARSIStrategy().execute(df)
        srv1 = SupportResistanceV1(plots_queue, file_to_save)
        srv1MarkersFn, _ = srv1.execute(df)
        Plot(df, plots_queue, contract).plot(marsiStrategyMarkersFn, srv1MarkersFn)

    for _contract in data["contracts"]:
        candlestick_data = []
        fields = str.split(_contract, ",")
        contract = Contract()
        contract.symbol = fields[0]
        contract.currency = fields[1]
        contract.secType = fields[2]
        contract.exchange = fields[3]

        interval = args.interval
        timePeriod = args.bar_size

        file_to_save = "data/data-{}-{}-{}-{}-{}-{}.csv".format(
            contract.symbol,
            contract.secType,
            contract.exchange,
            contract.currency,
            interval,
            timePeriod,
        )

        os.makedirs(os.path.dirname(file_to_save), exist_ok=True)
        technical_indicators = TechnicalIndicators(candlestick_data, file_to_save)
        rhd_object = rhd.RequestHistoricalData(client, callbackFnMap, contextMap)
        rhd_cb = rhd_callback.Callback(candlestick_data)

        if not os.path.exists(file_to_save) or args.refresh:
            rhd_object.request_historical_data(
                reqID=id_counter,
                contract=contract,
                interval=interval,
                timePeriod=timePeriod,
                dataType='MIDPOINT',
                rth=0,
                timeFormat=2,
                keepUpToDate=False,
                atDatapointFn=rhd_cb.handle,
                afterAllDataFn=process_contract_data,
                atDatapointUpdateFn=lambda x, y: None,
                technicalIndicators=technical_indicators,
                fileToSave=file_to_save,
                candlestickData=candlestick_data,
            )
            id_counter += 1
        else:
            df = pd.read_csv(file_to_save, index_col=[0])
            process_contract_data(df, technical_indicators, file_to_save, contract)

    # Drain plots
    while plots_queue:
        plots_queue.pop()()


def cmd_train_svm(args: argparse.Namespace):
    os.makedirs('data', exist_ok=True)
    plots_queue = []
    from machine_learning.svm_model_trainer import SVMModelTrainer
    trainer = SVMModelTrainer(plots_queue, args.output)
    # Expect user to provide a CSV path
    df = pd.read_csv(args.input, index_col=[0])
    trainer.process_data_with_file(df)


def cmd_train_lstm(args: argparse.Namespace):
    os.makedirs('data', exist_ok=True)
    plots_queue = []
    try:
        from machine_learning.lstm_model_trainer import LSTMModelTrainer
    except ModuleNotFoundError as e:
        raise SystemExit("TensorFlow/Keras not installed. For Apple Silicon: 'pip install tensorflow-macos tensorflow-metal' or install a compatible TensorFlow for your platform.") from e
    trainer = LSTMModelTrainer(plots_queue, args.output)
    df = pd.read_csv(args.input, index_col=[0])
    trainer.process_data(df)


def main():
    parser = argparse.ArgumentParser(description="Trading Bot CLI")
    sub = parser.add_subparsers(dest='command', required=True)

    p0 = sub.add_parser('fetch-process-plot', help='Fetch IBKR historical, compute indicators, run strategies, plot')
    p0.add_argument('--interval', default='6 M')
    p0.add_argument('--bar-size', default='1 hour')
    p0.add_argument('--refresh', action='store_true', help='Ignore cached CSVs')
    p0.set_defaults(func=cmd_fetch_process_plot)

    p1 = sub.add_parser('train-svm', help='Train SVM model from a CSV file')
    p1.add_argument('--input', required=True, help='Path to CSV file containing market data')
    p1.add_argument('--output', required=True, help='Path to save artifacts/plots')
    p1.set_defaults(func=cmd_train_svm)

    p2 = sub.add_parser('train-lstm', help='Train LSTM model from a CSV file')
    p2.add_argument('--input', required=True)
    p2.add_argument('--output', required=True)
    p2.set_defaults(func=cmd_train_lstm)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()



