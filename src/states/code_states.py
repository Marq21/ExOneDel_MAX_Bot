"""FSM-состояния для сценария отправки кода."""


class CodeStates:
    """Состояния FSM для MAX-бота."""
    CHOOSING_STORE = "choosing_store"
    RECEIVING_CODE = "receiving_code"
    CHOOSING_OFFICE = "choosing_office"
    WAITING_FOR_NAME = "waiting_for_name"
    WAITING_FOR_PHONE = "waiting_for_phone"