from __future__ import annotations

from functools import cached_property
from pathlib import Path
from traceback import format_exc


def deaccent(word):
    """replace non-ascii chars: î á ö í ü ñ é ó ú Á"""
    for x, y in [('á', 'a'), ('é', 'e'), ('í', 'i'), ('ó', 'o'), ('ú', 'u'),
                 ('ü', 'u'), ('î', 'i'), ('ö', 'o'), ('Á', 'a')]:
        word = word.replace(x, y)
    return word


def invert(word):
    return "".join(reversed(word))


class DictStorage:
    content: dict

    def __init__(self):
        self.content = {}

    def get(self, item, default=None):
        if item not in self.content:
            return default
        return self.content[item]

    def set(self, item, value):
        self.content[item] = value

    def update(self, item, **kwargs):
        element = self.content[item]
        for key, value in kwargs.items():
            setattr(element, key, value)

    def __iter__(self):
        return iter(self.content.values())

    def __contains__(self, item):
        return item in self.content


class WordsList:
    words: DictStorage

    def __init__(self, words: list[str], length=None):
        self.length = length
        self._words = [w for w in sorted(words) if not length or len(w) == length]
        self.words = DictStorage()
        self.l_and_p = {}
        self.setup()

    def setup(self):
        for word_str in self._words:
            word = Word(word_str)
            self.words.set(word.deaccented, word)
            self.register_word_letter_and_position(word)
            inverted = self.words.get(invert(word.deaccented))
            if inverted:
                word.inverted = inverted

    def iter_for_length(self, length: int):
        for word in self.words:
            if len(word) != length or word.inverted is None:
                continue
            yield word

    def register_word_letter_and_position(self, word: Word):
        for pos, letter in enumerate(word.deaccented):
            if (letter, pos) not in self.l_and_p:
                self.l_and_p[(letter, pos)] = set()
            self.l_and_p[(letter, pos)].add(word.deaccented)

    def word_for_letters_in_position(self, letters: str, position: int, length: int = None):
        for item in self.l_and_p.get((letters[0], position), []):
            if length and len(item) != length:
                continue
            candidate = self.words.get(item)
            if candidate.deaccented[position:position+len(letters)] != letters:
                continue
            yield candidate


class Inverted:
    def __get__(self, obj: Word, obj_type=None):
        return getattr(obj, "_inverted", None)

    def __set__(self, obj: Word, value: Word):
        obj._inverted = value
        if value is not None and value.inverted is None:
            value.inverted = obj


class Word:
    original: str
    deaccented: str
    inverted = Inverted()

    def __init__(self, original: str):
        self.original = original
        self.deaccented = deaccent(original)
        if self.is_symmetrical:
            self.inverted = self

    def __eq__(self, other: str | Word):
        if other is None:
            return False
        if isinstance(other, str):
            return self.deaccented == deaccent(other)
        return self.deaccented == other.deaccented

    def __lt__(self, other: Word):
        if other is None:
            return False
        return self.original < other.original

    def __len__(self):
        return len(self.deaccented)

    @cached_property
    def is_symmetrical(self):
        return self.deaccented == self.inverted_deaccented

    @cached_property
    def inverted_deaccented(self):
        return invert(self.deaccented)

    def __hash__(self):
        return hash(self.original)

    def __str__(self):
        return self.original

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.original} - symmetrical: {self.is_symmetrical}>"


class Sator:
    def __init__(self, length: int, content: list[Word] = None):
        assert not content or len(content) == length, f"content debe ser de longitud {length}"
        self.length = length
        self.content: list[Word | None] = content or [None for _ in range(length)]

    def __setitem__(self, pos: int, word: Word):
        assert word.inverted, f"{word} no es reversible"
        self.content[pos] = word
        if 2 * pos + 1 != self.length:
            self.content[self.length - pos - 1] = word.inverted

    def copy_with_word_in_pos(self, word: Word, pos: int):
        new_sator = self.__copy__()
        new_sator[pos] = word
        return new_sator

    def __hash__(self):
        return hash(tuple(sorted([w for w in self.content if w])))

    def __copy__(self):
        return Sator(self.length, self.content[:])

    def __repr__(self):
        r = f"<{self.__class__.__name__}: "
        tab = " " * len(r)
        return "\n".join(f"{tab if i else r}{self._fmt_word(w)}" for i, w in enumerate(self.content))+" >"

    def _fmt_word(self, word: Word | None):
        word_str = "-" * self.length if word is None else word.original.upper()
        return "  ".join(a for a in word_str)

    def __iter__(self):
        return iter(self.content)

    def __getitem__(self, slice):
        return self.content[slice]


class Satorter:
    def __init__(self, words: WordsList, length: int = None, near_miss=0):
        self.words = words
        self.near_miss = near_miss
        self.length = words.length or length
        assert self.length, "length must be specified if words has no fixed length attr"
        self.results = set()

    def __iter__(self):
        return self.generator()

    def run(self):
        for _ in self.generator():
            pass

    def generator(self):
        for word in self.words.iter_for_length(self.length):
            if self.length % 2 and not word.is_symmetrical:
                continue
            try:
                for result in self.iter_sator_for_central(word):
                    if result in self.results:
                        continue
                    self.results.add(result)
                    yield result
            except Exception as e:
                print(format_exc())
                print("Sator when error: \n", sator)

    def iter_sator_for_central(self, running_word: Word, pos: int = None, sator: Sator = None):
        sator = sator or Sator(self.length)
        pos = self.middle_pos if pos is None else pos
        new_sator = sator.copy_with_word_in_pos(running_word.inverted, pos)
        if pos == 0:
            yield new_sator
        else:
            required = "".join(w.deaccented[pos-1] for w in new_sator[pos:self.length - pos])
            no_words = True
            for running_word in self.words.word_for_letters_in_position(required, pos, self.length):
                if not running_word.inverted:
                    continue
                no_words = False
                for inner_sator in self.iter_sator_for_central(running_word, pos - 1, new_sator):
                    yield inner_sator
            if no_words and self.near_miss >= pos:
                yield new_sator

    @cached_property
    def middle_pos(self):
        return (self.length + 1) // 2 - 1


if __name__ == "__main__":
    original_list = Path("listado.txt").open().read().split("\n")
    MAX_LENGTH = max(len(w) for w in original_list)
    print("max_length", MAX_LENGTH)

    for length in range(2, MAX_LENGTH + 1):

        words_list = WordsList(original_list, length)
        for i, sator in enumerate(Satorter(words_list, near_miss=1)):
            print("\n" + str(sator) + f" length {length} (#{i})")
