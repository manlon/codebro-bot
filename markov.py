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

    @classmethod
    def triples(cls, words):
        if len(words) < 3:
            return
        for i in range(len(words) - 2):
            yield (words[i], words[i+1], words[i+2])

    def _ignore(self, word: str):
        word.strip("\'\"!@#$%^&*().,/\\+=<>?:;").upper() in self.ignore_words

    def tokenize(self, sentence: str):
        words = [w for w in sentence.split() if not self._ignore(w)]
        if not words:
            return

        yield START
        for w in words:
            if any(c in w for c in ('.', '?', '!')):
                yield STOP
                yield w.strip(".?!")
                yield START
            else:
                yield w
        yield STOP

    def update_cache(self, new_sentence = None): 
        if new_sentence:
            db = self.cache
            words = list(self.tokenize(new_sentence))
        else:
            db = {START: []}
            words = self.words

        start_of_chain = True
        for w1, w2, w3 in self.triples(words):
            if w1 in (START, STOP) or w2 in (START, STOP) or w3 == START:
                start_of_chain = True
            else:
                if start_of_chain:
                    if w1 not in db[START]:
                        db[START].append(w1)
                    next_words = db.setdefault(w1, [])
                    if w2 not in next_words:
                        next_words.append(w2)
                    start_of_chain = False
                next_words = db.setdefault((w1, w2), [])
                if w3 not in next_words:
                    next_words.append(w3)
        self.cache = db

    def update_corpus(self, sentence: str):
        new_words = list(self.tokenize(sentence))
        if not new_words:
            return
        self.words += new_words
        lk = None
        if not self.skip_mp:
            lk = Lock()
        with open(self.brain_file, 'w') as outfile:
            if not self.skip_mp:
                lk.acquire()
            outfile.write(yaml.dump(list(self.words), default_flow_style=True))
            if not self.skip_mp:
                lk.release()

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

    def create_response(self, prompt="", learn=False):
        # set seedword from somewhere in words if there's no prompt
        prompt_tokens = prompt.split()
        valid_seeds = [tok for tok in prompt_tokens[:-2] if tok in self.cache and tok != START]
        seed_word = random.choice(valid_seeds) if valid_seeds else None
        response = self.generate_markov_text(seed_word)
        if learn:
            if self.skip_mp:
                self.update_corpus(prompt)
            else:
                Process(target=self.update_corpus, args=(prompt,)).start()
            self.update_cache(prompt)
        return response
