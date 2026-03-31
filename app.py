from fastapi import FastAPI

app = FastAPI()

def fibonacci(n):
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    elif n == 2:
        return [0, 1]
    else:
        fib_sequence = [0, 1]
        for i in range(2, n):
            next_value = fib_sequence[-1] + fib_sequence[-2]
            fib_sequence.append(next_value)
        return fib_sequence

@app.get("/fibonacci/{n}", description="Return the first n numbers of the Fibonacci sequence")
async def get_fibonacci(n: int):
    if n < 0:
        return {"error": "Input must be a non-negative integer"}
    return {"fibonacci_sequence": fibonacci(n)}
