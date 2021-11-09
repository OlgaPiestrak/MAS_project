from os import getcwd

from cbsr.factory import CBSRfactory
from nltk import download
from nltk.data import path

from sentiment_service import SentimentAnalysisService


class SentimentAnalysisFactory(CBSRfactory):
    def __init__(self):
        super(SentimentAnalysisFactory, self).__init__()

    def get_connection_channel(self):
        return 'sentiment_analysis'

    def create_service(self, connect, identifier, disconnect):
        return SentimentAnalysisService(connect, identifier, disconnect)


if __name__ == '__main__':
    cwd = getcwd()
    download('punkt', download_dir=cwd)
    download('averaged_perceptron_tagger', download_dir=cwd)
    download('wordnet', download_dir=cwd)
    path.append(cwd)

    sentiment_analysis_factory = SentimentAnalysisFactory()
    sentiment_analysis_factory.run()
