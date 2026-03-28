class Calculator:
    """
    Calculator class provides basic arithmetic operations.
    """

    def add(self, a: float, b: float) -> float:
        """
        Add two numbers and return the result.

        Args:
            a (float): The first number to add.
            b (float): The second number to add.

        Returns:
            float: The sum of the two numbers.
        """
        return a + b

    def subtract(self, a: float, b: float) -> float:
        """
        Subtract the second number from the first and return the result.

        Args:
            a (float): The number from which to subtract.
            b (float): The number to subtract.

        Returns:
            float: The result of the subtraction.
        """
        return a - b

    def multiply(self, a: float, b: float) -> float:
        """
        Multiply two numbers and return the result.

        Args:
            a (float): The first number to multiply.
            b (float): The second number to multiply.

        Returns:
            float: The product of the two numbers.
        """
        return a * b

    def divide(self, a: float, b: float) -> float:
        """
        Divide the first number by the second and return the result.

        Args:
            a (float): The number to be divided.
            b (float): The number by which to divide.

        Returns:
            float: The result of the division.

        Raises:
            ValueError: If the divisor is zero.
        """
        if b == 0:
            raise ValueError("Cannot divide by zero.")
        return a / b
