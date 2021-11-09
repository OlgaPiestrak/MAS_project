from pickle import load
from re import sub
from string import punctuation

from cbsr.service import CBSRservice
from nltk.stem.wordnet import WordNetLemmatizer
from nltk.tag import pos_tag
from nltk.tokenize import word_tokenize


class SentimentAnalysisService(CBSRservice):
    def __init__(self, connect, identifier, disconnect):
        super(SentimentAnalysisService, self).__init__(connect, identifier, disconnect)
        with open('classifier.pickle', 'rb') as pickle:
            self.classifier = load(pickle)
        self.lemmatizer = WordNetLemmatizer()

    def get_device_types(self):
        return ['mic']

    def get_channel_action_mapping(self):
        return {self.get_full_channel('text_transcript'): self.execute}

    def execute(self, message):
        sentence = message['data'].decode()
        tokens = self.remove_noise(word_tokenize(sentence))
        sentiment = self.classifier.classify(dict([token, True] for token in tokens))
        print(sentiment)
        self.publish('text_sentiment', sentiment)

    def remove_noise(self, tokens):
        cleaned_tokens = []
        for token, tag in pos_tag(tokens):
            token = sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+#]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', token)
            token = sub('(@[A-Za-z0-9_]+)', '', token)

            if tag.startswith('NN'):
                pos = 'n'
            elif tag.startswith('VB'):
                pos = 'v'
            else:
                pos = 'a'

            token = self.lemmatizer.lemmatize(token, pos)
            if len(token) > 0 and token not in punctuation:
                cleaned_tokens.append(token.lower())

        return cleaned_tokens
