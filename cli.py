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
# Other strategies are imported lazily in cmd_fetch_process_plot to avoid
# unnecessary imports when not used.


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

    def process_contract_data(df, technical_indicators, file_to_save, contract, candlestick_data):
        df = technical_indicators.execute(df)

        # Default to MARSI and Support/Resistance V1 if no strategies are explicitly selected
        has_any_strategy = (args.use_rsi or args.use_hammer or args.use_marsi or
                           args.use_support_resistance_v1 or args.use_support_resistance or
                           args.use_lstm or args.use_svm_trainer)
        use_marsi = args.use_marsi or (not has_any_strategy)
        use_support_resistance_v1 = args.use_support_resistance_v1 or (not has_any_strategy)

        # Strategy markers functions to collect
        strategy_markers_fns = []

        # RSI Strategy
        if args.use_rsi:
            from rsi_strategy.rsi_strategy import RSIStrategy
            rsi_markers = RSIStrategy().execute(df)
            if rsi_markers:
                strategy_markers_fns.append(rsi_markers)

        # Hammer Shooting Star Pattern
        if args.use_hammer:
            from hammer_shooting_star.hammer_shooting_star import HammerShootingStar
            hammer_markers = HammerShootingStar().execute(df)
            if hammer_markers:
                strategy_markers_fns.append(hammer_markers)

        # MARSI Strategy
        if use_marsi:
            marsi_markers = MARSIStrategy().execute(df)
            if marsi_markers:
                strategy_markers_fns.append(marsi_markers)

        # Support/Resistance V1
        srv1_markers_fn = None
        y_lines = None
        if use_support_resistance_v1:
            srv1 = SupportResistanceV1(plots_queue, file_to_save)
            srv1_markers_fn, y_lines = srv1.execute(df)

        # Support/Resistance (alternative)
        if args.use_support_resistance:
            from support_resistance.support_resistance import SupportResistance
            sr = SupportResistance(candlestick_data, plots_queue, file_to_save)
            sr.process_data_with_file(df)

        # LSTM Model Trainer
        if args.use_lstm:
            try:
                from machine_learning.lstm_model_trainer import LSTMModelTrainer
                lstm_trainer = LSTMModelTrainer(plots_queue, file_to_save)
                lstm_trainer.process_data(df)
            except ModuleNotFoundError as e:
                print(f"Warning: LSTM trainer not available: {e}")

        # SVM Model Trainer
        if args.use_svm_trainer:
            from machine_learning.svm_model_trainer import SVMModelTrainer
            svm_trainer = SVMModelTrainer(plots_queue, file_to_save)
            df, model = svm_trainer.process_data_with_file(df)

        # Plot with all strategy markers
        # Use the first strategy markers function if available, otherwise None
        primary_markers = strategy_markers_fns[0] if strategy_markers_fns else None
        Plot(df, plots_queue, contract).plot(primary_markers, srv1_markers_fn)

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
                afterAllDataFn=lambda df, ti, fts, c: process_contract_data(df, ti, fts, c, candlestick_data),
                atDatapointUpdateFn=lambda x, y: None,
                technicalIndicators=technical_indicators,
                fileToSave=file_to_save,
                candlestickData=candlestick_data,
            )
            id_counter += 1
        else:
            df = pd.read_csv(file_to_save, index_col=[0])
            process_contract_data(df, technical_indicators, file_to_save, contract, candlestick_data)

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
    p0.add_argument('--interval', default='6 M', help='Time interval for historical data (e.g., "6 M")')
    p0.add_argument('--bar-size', default='1 hour', help='Bar size (e.g., "1 hour", "15 mins")')
    p0.add_argument('--refresh', action='store_true', help='Ignore cached CSVs and re-fetch from IBKR')

    # Strategy selection flags
    p0.add_argument('--use-rsi', action='store_true', help='Run RSI Strategy')
    p0.add_argument('--use-hammer', action='store_true', help='Run Hammer Shooting Star pattern detection')
    p0.add_argument('--use-marsi', action='store_true', help='Run MARSI Strategy (default: enabled if no strategies specified)')
    p0.add_argument('--use-support-resistance-v1', action='store_true', help='Run Support/Resistance V1 (default: enabled if no strategies specified)')
    p0.add_argument('--use-support-resistance', action='store_true', help='Run Support/Resistance (alternative implementation)')
    p0.add_argument('--use-lstm', action='store_true', help='Run LSTM model trainer')
    p0.add_argument('--use-svm-trainer', action='store_true', help='Run SVM model trainer')

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



