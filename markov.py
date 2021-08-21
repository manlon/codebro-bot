import yaml
import random
from multiprocess import Lock, Manager, Process

BACKUP_FILE = "codebro.yaml"
IGNORE_WORDS = ["CODEBRO", u"CODEBRO"]


# instantiate a Markov object with the source file
class Markov():
    def __init__(self, source_file: str):
        self.manager = Manager()
        self.words = self.manager.list(self.load_corpus(source_file))
        self.cache = self.manager.dict(self.database(self.words, {}))

    def load_corpus(self, source_file: str):
        with open(source_file, 'r') as infile:
            return yaml.load(infile.read(), Loader=yaml.Loader)

    def generate_markov_text(self, words: list, cache: dict, seed_phrase=None):
        if seed_phrase:
            w1, w2 = seed_phrase[:2]
        else:
            valid_starts = [(x[0], x[1]) for x in cache.keys() if x[0] == "<START>"]
            w1, w2 = random.choice(valid_starts)

        gen_words = []
        while True:
            if w2 == "<STOP>":
                break
            w1, w2 = w2, random.choice(cache[(w1, w2)])
            gen_words.append(w1)

        message = ' '.join(gen_words)
        return message

    def triples(self, words):
        if len(words) < 3:
            return
        for i in range(len(words) - 2):
            yield (words[i], words[i+1], words[i+2])

    def database(self, words: list, cache: dict):
        for w1, w2, w3 in self.triples(words):
            key = (w1, w2)
            if key in cache:
                if not (w3 in cache[key]):
                    cache[key].append(w3)
            else:
                cache[key] = [w3]
        return cache

    def learn(self, sentence: str):
        tokens = sentence.split()

        # strip, uppercase, and check for inclusion in IGNORE_WORDS list
        is_ignored = lambda x: x.strip("\'\"!@#$%^&*().,/\\+=<>?:;").upper() in IGNORE_WORDS
        tokens = [x for x in tokens if not is_ignored(x)]
        if not tokens:
            return  # nothing to learn here!

        tokens[-1] = tokens[-1].strip(".?!")
        tokens = [u"<START>", *tokens, u"<STOP>"]
        indexes_with_stops = [tokens.index(x) for x in tokens if x.strip(".?!") != x]
        for i in indexes_with_stops[::-1]:
            tokens[i] = tokens[i].strip(".?!")
            tokens.insert(i + 1, u"<STOP>")
            tokens.insert(i + 2, u"<START>")

        self.words += tokens
        self.cache = self.database(self.words, {})
        lk = Lock()
        # there must be a better way to serialize from the proxy ..
        local_words = [word for word in self.words]
        with open('codebro.yaml', 'w') as outfile:
            with lk:
                outfile.write(yaml.dump(local_words, default_flow_style=True))

    def create_response(self, prompt="", learn=False):
        # set seedword from somewhere in words if there's no prompt
        prompt_tokens = prompt.split() or [random.choice(self.words)]

        # create a set of lookups for phrases that start with words
        # contained in prompt phrase
        seed_tuples = [("<START>", tok) for tok in prompt_tokens[:-2]]

        # lookup seeds in cache; compile a list of 'hits'
        valid_seeds = [seed for seed in seed_tuples if seed in self.cache]

        # either seed the lookup with a randomly selected valid seed,
        # or if there were no 'hits' generate with no seedphrase
        seed_phrase = random.choice(valid_seeds) if valid_seeds else None
        response = self.generate_markov_text(self.words, self.cache, seed_phrase)

        if learn:
            Process(target=self.learn, args=(prompt,)).start()
        return response
