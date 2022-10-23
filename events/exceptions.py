

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
