import concurrent.futures
import threading
import typing as t

__all__ = ["run_in_threads"]

T = t.TypeVar("T")


def run_in_threads(func: t.Callable[[int], T], *, threads: int = 8) -> list[T]:
    """Run a function in several threads at once, as parallel as the interpreter allows.

    Every thread waits on a barrier before calling it, so they all start together and contend for whatever it shares.

    :param func: Function to run, given the index of its thread.
    :param threads: How many threads to run it in.
    :return: What each thread returned, in thread order.
    :raises Exception: The first exception a thread raised.
    """
    barrier = threading.Barrier(threads)

    def target(index: int) -> T:
        barrier.wait()
        return func(index)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        return list(executor.map(target, range(threads)))
