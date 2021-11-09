from cbsr.factory import CBSRfactory

from sentiment_service import SentimentAnalysisService


class SentimentAnalysisFactory(CBSRfactory):
    def __init__(self):
        super(SentimentAnalysisFactory, self).__init__()

    def get_connection_channel(self):
        return 'corona_check'

    def create_service(self, connect, identifier, disconnect):
        return SentimentAnalysisService(connect, identifier, disconnect)


if __name__ == '__main__':
    sentiment_analysis_factory = SentimentAnalysisFactory()
    sentiment_analysis_factory.run()
