

class ParticipantNotFoundError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)

    def __str__(self):
        return "Участник не найден."


class DuplicateParticipantError(Exception):
    def __init__(self, *args, **kwargs):
        super().__init__(*args)

    def __str__(self):
        return "Такой участник уже зарегистрирован."


class ParticipantTooYoungError(Exception):
    def __init__(self, age=None, *args, **kwargs):
        super().__init__(*args)
        self.age = age

    def __str__(self):
        return f"Минимальный возраст участника: {self.age} лет."


class EntryClosedError(Exception):
    def __str__(self):
        return "Ввод результатов закрыт."


class RegistrationClosedError(Exception):
    def __str__(self):
        return "Регистрация закрыта."


class ResultsUpdateNotAllowedError(Exception):
    def __str__(self):
        return "Повторный ввод результатов запрещён."


class SetFullError(Exception):
    def __str__(self):
        return "В выбранном сете нет мест."


class InvalidResultsError(Exception):
    """Результаты не прошли проверку. routes — номера трасс (с единицы), на которых нашли ошибку,
    participant_id — чьи результаты, если проверяли сразу нескольких участников."""

    def __init__(self, message=None, routes=None, participant_id=None, *args):
        super().__init__(*args)
        self.message = message
        self.routes = routes or []
        self.participant_id = participant_id

    def __str__(self):
        if self.message:
            return self.message
        return f"Зона позже топа на трассах: {', '.join(str(r) for r in self.routes)}."


class WithoutRegistrationDisabledError(Exception):
    def __str__(self):
        return "Для этого события ввод без регистрации отключён."


class RegistrationNotNeededError(Exception):
    def __str__(self):
        return "Регистрация на это событие не нужна: имя, группу и сет укажите вместе с результатами."


class PayUnavailableError(Exception):
    def __str__(self):
        return "Оплата временно недоступна."
