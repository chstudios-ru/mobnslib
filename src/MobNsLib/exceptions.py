class NoDataInResponse(Exception):
    def __init__(self, message="No expected data in response"):
        super().__init__(message)

class NotJSONResponse(Exception):
    def __init__(self, message="Response is not JSON"):
        super().__init__(message)

class UnexpectedResponse(Exception):
    def __init__(self, message="Unexpected response"):
        super().__init__(message)

class WrongLoginOrPassword(Exception):
    def __init__(self, message="Wrong login or password"):
        super().__init__(message)

class NoExpectedData(Exception):
     def __init__(self, message="No expected data"):
        super().__init__(message)
