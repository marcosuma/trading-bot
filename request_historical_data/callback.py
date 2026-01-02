from ibapi.ticktype import TickTypeEnum
from config import DEBUG


class Callback:
    def __init__(self, candlestickData):
        self.candlestickData = candlestickData

    def handleAlibaba(self, reqId, bar):
        # print("Alibaba data")
        self._handleBase(reqId, bar)

    def handleEnel(self, reqId, bar):
        # print("Enel data")
        self._handleBase(reqId, bar)

    def handleGld(self, reqId, bar):
        # print("Gld data")
        self._handleBase(reqId, bar)

    def handleEurUsd(self, reqId, bar):
        # print("EUR/USD data")
        self._handleBase(reqId, bar)

    def handleBitcoinFutures(self, reqId, bar):
        # print("Bitcoin Futures data")
        self._handleBase(reqId, bar)

    def handle(self, reqId, bar):
        if DEBUG:
            print("bar: ", bar)
        self._handleBase(reqId, bar)

    def _handleBase(self, reqId, bar):
        self.candlestickData.append(
            [
                str(bar.date),
                float(bar.open),
                float(bar.close),
                float(bar.high),
                float(bar.low),
                float(bar.volume),
            ]
        )
