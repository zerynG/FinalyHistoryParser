# parsing_modes.py
import csv
import os
from datetime import datetime
import time


class ParsingModes:
    def __init__(self, driver, parser):
        self.driver = driver
        self.parser = parser
        self.existing_data_file = "fon_bet_data2.csv"

    def mode_incremental_parsing(self):
        """Режим 2: Инкрементальный парсинг - обрабатывает N событий, сохраняет только новые"""
        print("\n🔄 РЕЖИМ ИНКРЕМЕНТАЛЬНОГО ПАРСИНГА")
        print("=" * 50)

        try:
            max_events_to_process = int(input("Введите количество событий для обработки: "))
        except ValueError:
            print("❌ Неверное число!")
            return

        # Загружаем существующие купоны и выводим отладочную информацию
        existing_coupons = self._load_existing_coupons_with_debug()
        print(f"📊 В базе уже есть {len(existing_coupons)} событий")

        # Начинаем парсинг с верха
        self.parser.scroll_to_top()
        time.sleep(3)

        processed_count = 0  # Всего обработано событий
        new_events_count = 0  # Новых событий найдено
        consecutive_empty_scrolls = 0
        max_empty_scrolls = 5

        # Список для хранения новых событий перед сохранением
        new_events = []

        while processed_count < max_events_to_process and consecutive_empty_scrolls < max_empty_scrolls:
            # Парсим видимые ставки
            visible_coupons = self.parser.get_visible_coupon_numbers()
            print(f"👀 Найдено видимых купонов: {len(visible_coupons)}")

            batch_processed = 0

            for coupon in visible_coupons:
                if coupon in self.parser.parsed_events:
                    continue

                if processed_count >= max_events_to_process:
                    break

                # Получаем информацию о ставке
                bet_info = self.parser.get_bet_info_by_coupon(coupon)
                if not bet_info:
                    print(f"❌ Не удалось получить информацию для: {coupon}")
                    continue

                # Проверяем статус ставки
                bet_result = bet_info.get('result', '')

                # Пропускаем "Не рассчитано"
                if "Не рассчитано" in bet_result:
                    print(f"⏳ [{processed_count + 1}/{max_events_to_process}] Пропускаем - не рассчитано: {coupon}")
                    self.parser.parsed_events.add(coupon)
                    processed_count += 1
                    batch_processed += 1
                    continue

                processed_count += 1
                batch_processed += 1

                # Проверяем, есть ли уже в базе (с отладкой)
                if coupon in existing_coupons:
                    print(f"ℹ️ [{processed_count}/{max_events_to_process}] Уже в базе: {coupon}")
                    self.parser.parsed_events.add(coupon)
                else:
                    print(
                        f"🎯 [{processed_count}/{max_events_to_process}] НОВОЕ событие: {coupon} (результат: {bet_result})")
                    print(f"🔍 Проверка: {coupon} НЕТ в existing_coupons")

                    # Парсим полную информацию
                    parsed_data = self._parse_complete_bet(coupon, bet_info)
                    if parsed_data:
                        new_events.append(parsed_data)
                        new_events_count += 1
                        print(f"✅ [{processed_count}/{max_events_to_process}] Успешно спаршено: {coupon}")
                        # Добавляем в existing_coupons чтобы не парсить повторно
                        existing_coupons.add(coupon)
                    else:
                        print(f"❌ [{processed_count}/{max_events_to_process}] Ошибка парсинга: {coupon}")

            if batch_processed > 0:
                consecutive_empty_scrolls = 0
            else:
                consecutive_empty_scrolls += 1
                print(f"⚠️ Новых событий не найдено (пустых прокруток: {consecutive_empty_scrolls})")

            # Прокручиваем дальше если нужно больше событий
            if processed_count < max_events_to_process and consecutive_empty_scrolls < max_empty_scrolls:
                print("🔄 Прокручиваем для поиска новых событий...")
                if not self.parser.scroll_step_by_step():
                    print("❌ Не удалось прокрутить дальше")
                    break

        # Сохраняем все новые события с правильной сортировкой
        if new_events:
            print(f"💾 Сохраняем {len(new_events)} новых событий...")
            self._save_new_events_sorted(new_events)

        print(f"\n✅ Инкрементальный парсинг завершен.")
        print(f"📊 Обработано событий: {processed_count}")
        print(f"📈 Добавлено новых событий: {new_events_count}")

    def _parse_complete_bet(self, coupon_number, bet_info):
        """Полностью парсит ставку и возвращает данные"""
        try:
            print(f"🔍 Начинаем парсинг ставки {coupon_number}...")
            print(f"📋 Основная информация: {bet_info.get('pari_type', '')} - {bet_info.get('result', '')}")

            # Обрабатываем проигрыши - исправляем суммы
            if "Проигрыш" in bet_info.get('result', ''):
                if not bet_info.get('stake_amount') and bet_info.get('win_amount'):
                    bet_info['stake_amount'] = bet_info['win_amount']
                    bet_info['win_amount'] = '-' + bet_info['win_amount']
                elif not bet_info.get('stake_amount'):
                    bet_info['stake_amount'] = '330'
                    bet_info['win_amount'] = '-330'

            # Получаем детали через развертывание
            detail_info = None
            if self.parser.expand_bet(coupon_number):
                print(f"📖 Получаем детали для {coupon_number}...")
                detail_info = self.parser.get_expanded_details()
                print(f"📖 Детали получены: {bool(detail_info)}")

                if "Экспресс" in bet_info.get('pari_type', ''):
                    express_events = self.parser.get_express_events()
                    if express_events:
                        detail_info['express_events'] = express_events
                        print(f"🎪 Найдено событий экспресса: {len(express_events)}")

                self.parser.close_all_expanded_bets()

            # Сохраняем данные
            if detail_info:
                combined_info = {**bet_info, **detail_info, 'expanded': True}
            else:
                combined_info = {**bet_info, 'expanded': False}

            # Добавляем в данные парсера
            self.parser.data.append(combined_info)
            self.parser.parsed_events.add(coupon_number)

            return combined_info

        except Exception as e:
            print(f"❌ Критическая ошибка при парсинге {coupon_number}: {e}")
            return None

    def _save_new_events_sorted(self, new_events):
        """Сохраняет новые события с сортировкой по дате и времени (самые свежие вверху)"""
        try:
            # Сортируем новые события по дате и времени (самые свежие первые)
            sorted_new_events = self._sort_events_by_datetime(new_events)
            print(f"📊 Новые события отсортированы по дате/времени")

            # Загружаем существующие данные
            existing_data = []
            file_exists = os.path.isfile(self.existing_data_file)

            if file_exists:
                with open(self.existing_data_file, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    existing_data = list(reader)
                print(f"📊 Загружено {len(existing_data)} существующих записей")

            # Объединяем данные: новые отсортированные события + существующие
            all_data = sorted_new_events + existing_data

            # Сохраняем все данные
            self._save_all_data_to_csv(all_data)
            print(f"💾 Все данные сохранены с правильной сортировкой")

        except Exception as e:
            print(f"❌ Ошибка при сохранении новых событий: {e}")

    def _sort_events_by_datetime(self, events):
        """Сортирует события по дате и времени (самые свежие вначале)"""

        def parse_datetime(event):
            try:
                # Пытаемся извлечь дату и время из start_time
                if event.get('start_time'):
                    datetime_str = event['start_time']
                    # Формат: "DD.MM.YYYY HH:MM"
                    return datetime.strptime(datetime_str, '%d.%m.%Y %H:%M')

                # Если start_time нет, используем время ставки и текущую дату
                if event.get('time'):
                    time_str = event['time']
                    current_date = datetime.now().strftime('%d.%m.%Y')
                    datetime_str = f"{current_date} {time_str}"
                    return datetime.strptime(datetime_str, '%d.%m.%Y %H:%M:%S')

                # Если ничего нет, возвращаем минимальную дату
                return datetime.min

            except Exception as e:
                print(f"⚠️ Ошибка парсинга даты для события {event.get('coupon_number', 'N/A')}: {e}")
                return datetime.min

        # Сортируем по убыванию (самые свежие сначала)
        return sorted(events, key=parse_datetime, reverse=True)

    def _save_all_data_to_csv(self, data):
        """Сохраняет все данные в CSV файл"""
        fieldnames = [
            'coupon_number', 'time', 'pari_type', 'description', 'factor', 'result',
            'stake_amount', 'win_amount', 'start_time', 'event', 'pari',
            'detail_factor', 'score', 'detail_result', 'expanded', 'express_events'
        ]

        try:
            with open(self.existing_data_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for row in data:
                    new_row = {}
                    for field in fieldnames:
                        if field == 'express_events' and field in row and row[field]:
                            events_list = []
                            for event in row[field]:
                                events_list.append(
                                    f"{event.get('event', '')}: {event.get('pari', '')} - {event.get('result', '')}")
                            new_row[field] = '; '.join(events_list)
                        else:
                            new_row[field] = row.get(field, '')
                    writer.writerow(new_row)

            print(f"💾 Всего записей в файле: {len(data)}")
            return True

        except Exception as e:
            print(f"❌ Ошибка при сохранении данных: {e}")
            return False

    def _load_existing_coupons_with_debug(self):
        """Загружает номера купонов из существующего файла с отладочной информацией"""
        existing_coupons = set()

        if os.path.exists(self.existing_data_file):
            try:
                print(f"📁 Загружаем данные из файла: {self.existing_data_file}")
                with open(self.existing_data_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    row_count = 0
                    for row in reader:
                        row_count += 1
                        if 'coupon_number' in row and row['coupon_number']:
                            coupon = row['coupon_number'].strip()
                            existing_coupons.add(coupon)
                            # Выводим первые 5 купонов для отладки
                            if row_count <= 5:
                                print(f"   [{row_count}] coupon_number: '{coupon}'")

                    print(f"📊 Всего строк в файле: {row_count}")
                    print(f"📊 Уникальных купонов загружено: {len(existing_coupons)}")

                    # Проверяем конкретные купоны
                    test_coupons = ['18518380498', '18502960160', '18502945161']
                    for test_coupon in test_coupons:
                        if test_coupon in existing_coupons:
                            print(f"✅ Купон {test_coupon} найден в базе")
                        else:
                            print(f"❌ Купон {test_coupon} ОТСУТСТВУЕТ в базе")

            except Exception as e:
                print(f"❌ Не удалось загрузить существующие данные: {e}")
        else:
            print("📁 Файл с данными не найден, будет создан новый")

        return existing_coupons

    def mode_date_parsing(self):
        """Режим 1: Парсинг по дате с дозаписью в файл"""
        print("\n📅 РЕЖИМ ПАРСИНГА ПО ДАТЕ")
        print("=" * 50)

        target_date = input("Введите дату для парсинга (в формате ДД.ММ.ГГГГ): ").strip()

        # Валидация даты
        try:
            datetime.strptime(target_date, '%d.%m.%Y')
        except ValueError:
            print("❌ Неверный формат даты! Используйте ДД.ММ.ГГГГ")
            return

        print(f"🎯 Ищем события за {target_date}...")

        # Загружаем существующие данные
        existing_coupons = self._load_existing_coupons_with_debug()

        # Начинаем парсинг с верха
        self.parser.scroll_to_top()
        time.sleep(3)

        parsed_count = 0
        found_target_date = False
        consecutive_other_dates = 0
        max_consecutive_other_dates = 3

        # Список для новых событий
        new_events = []

        while not found_target_date and consecutive_other_dates < max_consecutive_other_dates:
            # Получаем видимые купоны
            visible_coupons = self.parser.get_visible_coupon_numbers()

            for coupon in visible_coupons:
                if coupon in self.parser.parsed_events:
                    continue

                # Получаем информацию о ставке
                bet_info = self.parser.get_bet_info_by_coupon(coupon)
                if not bet_info:
                    continue

                # Проверяем дату ставки
                bet_date = self._extract_date_from_bet(bet_info)

                if bet_date == target_date:
                    # Это нужная дата - парсим
                    if coupon not in existing_coupons:
                        parsed_data = self._parse_complete_bet(coupon, bet_info)
                        if parsed_data:
                            new_events.append(parsed_data)
                            parsed_count += 1
                            print(f"✅ Найдено новое событие: {coupon}")
                        else:
                            print(f"❌ Ошибка сохранения: {coupon}")
                    else:
                        print(f"ℹ️ Событие {coupon} уже есть в базе")
                        self.parser.parsed_events.add(coupon)

                    found_target_date = True
                    consecutive_other_dates = 0

                elif bet_date and bet_date < target_date:
                    # Более старая дата - продолжаем поиск
                    consecutive_other_dates = 0
                    print(f"📅 Более старая дата: {bet_date}, продолжаем поиск...")
                    self.parser.parsed_events.add(coupon)

                else:
                    # Другая дата (более новая или неизвестная)
                    consecutive_other_dates += 1
                    self.parser.parsed_events.add(coupon)
                    if consecutive_other_dates >= max_consecutive_other_dates:
                        print("🔚 Найдены события других дат, завершаем поиск...")
                        break

            # Прокручиваем дальше если не нашли нужную дату
            if not found_target_date and consecutive_other_dates < max_consecutive_other_dates:
                if not self.parser.scroll_step_by_step():
                    print("❌ Не удалось прокрутить дальше")
                    break

        # Сохраняем новые события с сортировкой
        if new_events:
            print(f"💾 Сохраняем {len(new_events)} новых событий...")
            self._save_new_events_sorted(new_events)

        print(f"\n✅ Парсинг по дате завершен. Найдено новых событий: {parsed_count}")

    def mode_full_rewrite_parsing(self):
        """Режим 3: Полная перезапись с выбором количества событий"""
        print("\n🔄 РЕЖИМ ПОЛНОЙ ПЕРЕЗАПИСИ")
        print("=" * 50)

        try:
            max_events = int(input("Введите количество событий для парсинга: "))
        except ValueError:
            print("❌ Неверное число!")
            return

        # Создаем временный файл
        temp_file = "temp_fon_bet_data.csv"

        # Устанавливаем лимит и очищаем данные
        self.parser.max_events = max_events
        self.parser.data = []
        self.parser.parsed_events = set()

        # Выполняем стандартный парсинг
        self.parser.parse_bets()

        # Сортируем данные перед сохранением
        sorted_data = self._sort_events_by_datetime(self.parser.data)
        print(f"📊 Данные отсортированы по дате/времени")

        # Сохраняем в временный файл
        self._save_all_data_to_csv(sorted_data)

        # Заменяем старый файл новым
        if os.path.exists(self.existing_data_file):
            backup_file = self.existing_data_file.replace('.csv', '_backup.csv')
            os.rename(self.existing_data_file, backup_file)
            print(f"💾 Создан бэкап старого файла: {backup_file}")

        os.rename(temp_file, self.existing_data_file)
        print(f"✅ Данные полностью перезаписаны в файл: {self.existing_data_file}")
        print(f"📊 Всего событий в новой базе: {len(self.parser.data)}")

    def _extract_date_from_bet(self, bet_info):
        """Извлекает дату из информации о ставке"""
        try:
            # Пытаемся извлечь дату из времени начала
            if bet_info.get('start_time'):
                date_part = bet_info['start_time'].split(' ')[0]
                return date_part

            # Альтернативно: из времени ставки (но это менее надежно)
            if bet_info.get('time'):
                # Предполагаем, что время ставки относится к текущей дате
                current_date = datetime.now().strftime('%d.%m.%Y')
                return current_date

        except Exception as e:
            print(f"❌ Ошибка при извлечении даты: {e}")

        return None


def select_parsing_mode(driver, parser):
    """Функция для выбора режима парсинга"""
    print("\n" + "=" * 50)
    print("🎯 ВЫБЕРИТЕ РЕЖИМ ПАРСИНГА:")
    print("=" * 50)
    print("1. 📅 Парсинг по дате (дозапись в файл)")
    print("2. 🔄 Инкрементальный парсинг (обработать N событий, добавить новые)")
    print("3. 🗂️ Полная перезапись (новый файл)")
    print("=" * 50)

    mode_selector = ParsingModes(driver, parser)

    while True:
        try:
            choice = int(input("Выберите режим (1-3): "))

            if choice == 1:
                mode_selector.mode_date_parsing()
                break
            elif choice == 2:
                mode_selector.mode_incremental_parsing()
                break
            elif choice == 3:
                mode_selector.mode_full_rewrite_parsing()
                break
            else:
                print("❌ Неверный выбор! Введите число от 1 до 3")

        except ValueError:
            print("❌ Пожалуйста, введите число от 1 до 3")

    return mode_selector