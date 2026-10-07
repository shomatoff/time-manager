"""EN: Shared interface translations. UZ: Interfeysning umumiy tarjimalari."""
LANGUAGES = {'en': 'English', 'ru': 'Русский', 'uz': 'O‘zbekcha'}
# Uzbek source strings keep the existing native interface compatible.
TEXT = {
    'POMODORO TAYMER': ('POMODORO TIMER', 'ТАЙМЕР POMODORO'),
    'Boshlashga tayyor': ('Ready to focus', 'Готовы к работе'),
    'O‘qish vaqti': ('Focus time', 'Время работы'),
    'Dars': ('Focus', 'Работа'),
    'Tanaffus': ('Break', 'Перерыв'),
    'Uzun tanaffus': ('Long break', 'Длинный перерыв'),
    'Boshlash': ('Start', 'Начать'),
    'Pauza': ('Pause', 'Пауза'),
    'Davom ettirish': ('Resume', 'Продолжить'),
    'To‘xtatish': ('Stop', 'Остановить'),
    'Tanaffusni o‘tkazish': ('Skip break', 'Пропустить перерыв'),
    'Darsga qaytish': ('Back to focus', 'Вернуться к работе'),
    '+1 daqiqa': ('+1 minute', '+1 минута'),
    'Esc — darsga qaytish': ('Esc — back to focus', 'Esc — вернуться к работе'),
    'Ko‘zingizni dam oldiring': ('Give your eyes a rest', 'Дайте глазам отдохнуть'),
    'Taymer pauzada': ('Timer paused', 'Таймер на паузе'),
    ' — pauza': (' — paused', ' — пауза'),
    'Vaqtlar · daqiqa': ('Durations · minutes', 'Длительность · минуты'),
    'Qo‘shimcha sozlamalar': ('More settings', 'Дополнительные настройки'),
    'Uzun tanaffus · daqiqa': ('Long break · minutes', 'Длинный перерыв · минуты'),
    'Har nechta darsdan so‘ng\n0 — uzun tanaffus o‘chiq': ('Sessions before long break\n0 — long break off', 'Занятий до длинного перерыва\n0 — длинный перерыв выключен'),
    'Tanaffus ovozi': ('Break sounds', 'Звуки перерыва'),
    'Kamaytirish': ('Decrease', 'Уменьшить'),
    'Ko‘paytirish': ('Increase', 'Увеличить'),
    'Oynani ochish': ('Open window', 'Открыть окно'),
    'Dasturdan chiqish': ('Quit application', 'Выйти из приложения'),
    'Tanaffusga 30 soniya qoldi': ('Break starts in 30 seconds', 'Перерыв через 30 секунд'),
    'Ishingizni saqlang yoki taymerni pauzaga qo‘ying.': ('Save your work or pause the timer.', 'Сохраните работу или поставьте таймер на паузу.'),
    'Oynani yopsangiz ham taymer tizim panelida davom etadi.\nVaqt o‘zgarishlari keyingi bosqichga qo‘llanadi.': ('The timer keeps running in the system tray when you close this window.\nDuration changes apply to the next phase.', 'После закрытия окна таймер продолжит работу в системном трее.\nИзменения времени применяются со следующего этапа.'),
    'Bajarilgan darslar: {count}': ('Completed sessions: {count}', 'Завершено занятий: {count}'),
    ' · Uzun tanaffus har {cycles} darsda': (' · Long break every {cycles} sessions', ' · Длинный перерыв каждые {cycles} занятий'),
    'Dastur allaqachon ishlayapti. Tizim panelidagi belgisini bosing.': ('The app is already running. Open it from the system tray.', 'Приложение уже запущено. Откройте его через значок в системном трее.'),
}


def translate(language, text, **values):
    suffix = ''
    if text.endswith((' ▸', ' ▾')):
        text, suffix = text[:-2], text[-2:]
    pair = TEXT.get(text)
    result = pair[0 if language == 'en' else 1] if pair and language in ('en', 'ru') else text
    return result.format(**values) + suffix
