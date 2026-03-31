def fibonacci(n):
    """
    Return the first n numbers of the Fibonacci sequence.

    :param n: Number of terms in the Fibonacci sequence to generate.
    :type n: int
    :return: List containing the first n Fibonacci numbers.
    :rtype: list
    """
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    
    fib_sequence = [0, 1]
    for i in range(2, n):
        next_value = fib_sequence[-1] + fib_sequence[-2]
        fib_sequence.append(next_value)
    
    return fib_sequence
