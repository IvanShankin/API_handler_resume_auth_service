from typing import List


class InfrastructureException(Exception):
    pass


class NotEnoughArguments(InfrastructureException):
    def __init__(self, args_list: List[str]):
        """
        :param args_list: Список аргументов, где хотя бы один из них должен быть передан
        """
        self.args_list = args_list
