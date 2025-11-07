from time import sleep
import scheduling


def connection_try_decorator(func):
    def wrapper(self, *args, **kwargs):
        max_tries = 3
        tries = 0
        while (tries <= max_tries):
            try:
                result = func(self, *args, **kwargs)
                return result
            except:
                print(f"An error occured. Retrying the request... ({tries}/{max_tries})")
                tries += 1
                sleep(5)

        if isinstance(self, scheduling.Process):
            self.error = True

        print("Reached the maximum number of tries. Aborting the process...")
        return None
    return wrapper