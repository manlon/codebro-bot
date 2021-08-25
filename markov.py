import yaml
import random
from multiprocess import Lock, Manager, Process

START = "<START>"
STOP = "<STOP>"

# instantiate a Markov object with the source file
class Markov:
    def __init__(self, brain_file: str, ignore_words, skip_mp=False):
        self.brain_file = brain_file
        self.ignore_words = ignore_words
        self.skip_mp = skip_mp
        if self.skip_mp:
            self.words = list(self.load_corpus(brain_file))
        else:
            self.manager = Manager()
            self.words = self.manager.list(self.load_corpus(brain_file))
        self.update_cache()

    @classmethod
    def load_corpus(cls, source_file: str):
        with open(source_file, 'r') as infile:
            return yaml.load(infile.read(), Loader=yaml.Loader)

    def generate_markov_text(self, seed=None):
        if seed:
            w1 = seed
        else:
            w1 = random.choice(self.cache[START])
        w2 = random.choice(self.cache[w1])

        gen_words = [w1]
        while True:
            if w2 == STOP:
                break
            w1, w2 = w2, random.choice(self.cache[(w1, w2)])
            gen_words.append(w1)

        message = ' '.join(gen_words)
        return message

    @classmethod
    def triples(cls, words):
        if len(words) < 3:
            return
        for i in range(len(words) - 2):
            yield (words[i], words[i+1], words[i+2])

    def update_cache(self):
        db = {START: set()}
        next_word_is_start = True
        for w1, w2, w3 in self.triples(self.words):
            if w1 in (START, STOP) or w2 in (START, STOP):
                next_word_is_start = True
            else:
                if next_word_is_start:
                    db[START].add(w1)
                    db.setdefault(w1, set()).add(w2)
                    next_word_is_start = False
                db.setdefault((w1, w2), set()).add(w3)
        self.cache = {key: list(val) for key, val in db.items()}

    @classmethod
    def tokenize(cls, words: list):
        yield START
        for w in words:
            if any(c in w for c in ('.', '?', '!')):
                yield STOP
                yield w.strip(".?!")
                yield START
            else:
                yield w
        yield STOP

    def learn(self, sentence: str):
        words = sentence.split()

        # strip, uppercase, and check for inclusion in IGNORE_WORDS list
        is_ignored = lambda x: x.strip("\'\"!@#$%^&*().,/\\+=<>?:;").upper() in self.ignore_words
        words = [x for x in words if not is_ignored(x)]
        if not words:
            return  # nothing to learn here!

        self.words += list(self.tokenize(words))
        self.update_cache()
        lk = None
        if not self.skip_mp:
            lk = Lock()
        with open(self.brain_file, 'w') as outfile:
            if not self.skip_mp:
                lk.acquire()
            outfile.write(yaml.dump(list(self.words), default_flow_style=True))
            if not self.skip_mp:
                lk.release()

    def create_response(self, prompt="", learn=False):
        # set seedword from somewhere in words if there's no prompt
        prompt_tokens = prompt.split()
        valid_seeds = [tok for tok in prompt_tokens[:-2] if tok in self.cache[START]]
        seed_word = random.choice(valid_seeds) if valid_seeds else None
        response = self.generate_markov_text(seed_word)
        if learn:
            if self.skip_mp:
                self.learn(prompt)
            else:
                Process(target=self.learn, args=(prompt,)).start()
        return response
