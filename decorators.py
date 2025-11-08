from time import sleep
from logging import getLogger
import scheduling

ENCODINGS = [
    ('.', '&123'), ('$', '&456'), ('#', '&789'),
    ('[', '&234'), (']', '&567'),
]

def encode_illegal_symbols(path:str) -> str:
    result = path
    for encoding in ENCODINGS:
        result = result.replace(encoding[0], encoding[1])
    return result

def decode_illegal_symbols(path:str) -> str:
    result = path
    for encoding in ENCODINGS:
        result = result.replace(encoding[1], encoding[0])
    return result


def connection_try_decorator(func):
    logger = getLogger()

    def wrapper(self, *args, **kwargs):
        max_tries = 3
        tries = 0
        while (tries <= max_tries):
            try:
                result = func(self, *args, **kwargs)
                return result
            except ConnectionError as e:
                print(f"An error occured. Retrying the request... ({tries}/{max_tries})")
                logger.error(str(e))
                tries += 1
                sleep(5)

        if isinstance(self, scheduling.Process):
            self.error = True

        print("Reached the maximum number of tries. Aborting the process...")
        return None
    return wrapper