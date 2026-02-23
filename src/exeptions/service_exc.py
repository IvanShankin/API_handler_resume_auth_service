
class ServiceException(Exception):
    pass


class UserBlockError(ServiceException):
    pass


class InvalidPassword(ServiceException):
    pass


class NotFoundRefreshToken(ServiceException):
    pass


class UserNotFoundServ(ServiceException):
    pass


class LoginIsBusy(ServiceException):
    pass


class InvalidJWTToken(ServiceException):
    pass

