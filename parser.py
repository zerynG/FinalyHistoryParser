# parser.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import csv
import os
import time
from datetime import datetime


class FonBetParser:
    def __init__(self, driver, max_events=15):
        self.driver = driver
        self.wait = WebDriverWait(driver, 20)
        self.max_events = max_events
        self.parsed_events = set()
        self.data = []
        self.retry_attempts = 3
        self.retry_delay = 2

    def scroll_to_top(self):
        """Прокрутка на самый верх"""
        try:
            scroll_block = self.driver.find_element(By.CSS_SELECTOR,
                                                    'div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO')
            self.driver.execute_script("arguments[0].scrollTop = 0;", scroll_block)
            time.sleep(3)
            print("✅ Прокрутка на верх завершена")
        except Exception as e:
            print(f"❌ Ошибка при прокрутке на верх: {e}")

    def get_visible_coupon_numbers(self):
        """Получает только видимые номера купонов в данный момент"""
        try:
            script = """
            var coupons = [];
            var virtualList = document.querySelector('div.virtual-list--FMDYy');
            if (!virtualList) return [];

            // Получаем видимую область
            var scrollContainer = document.querySelector('div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO');
            if (!scrollContainer) return [];

            var containerRect = scrollContainer.getBoundingClientRect();
            var containerTop = containerRect.top;
            var containerBottom = containerRect.bottom;

            var childDivs = virtualList.querySelectorAll('div[style*="top"]');

            for (var i = 0; i < childDivs.length; i++) {
                var div = childDivs[i];
                // Пропускаем sticky даты
                if (div.querySelector('.stickyDate--C07hV')) continue;

                var divRect = div.getBoundingClientRect();
                var divTop = divRect.top;
                var divBottom = divRect.bottom;

                // Проверяем, находится ли элемент в видимой области
                if (divTop >= containerTop && divBottom <= containerBottom) {
                    var couponElement = div.querySelector('.cellCouponNumber--K_lV2 span');
                    if (couponElement && couponElement.textContent.trim()) {
                        coupons.push(couponElement.textContent.trim());
                    }
                }
            }
            return coupons;
            """
            coupon_numbers = self.driver.execute_script(script)
            print(f"👀 Видимых номеров купонов: {len(coupon_numbers)}")
            return coupon_numbers
        except Exception as e:
            print(f"❌ Ошибка при получении видимых номеров купонов: {e}")
            return []

    def scroll_step_by_step(self, step_pixels=300):
        """Прокручивает пошагово и возвращает новые видимые элементы"""
        try:
            script = f"""
            var scrollBlock = document.querySelector('div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO');
            if (!scrollBlock) return false;

            var currentScroll = scrollBlock.scrollTop;
            scrollBlock.scrollTop = currentScroll + {step_pixels};
            return true;
            """

            result = self.driver.execute_script(script)
            time.sleep(2)  # Ждем обновления виртуального списка
            return result
        except Exception as e:
            print(f"❌ Ошибка при пошаговой прокрутке: {e}")
            return False

    def parse_visible_bets(self):
        """Парсит все видимые в данный момент ставки"""
        visible_coupons = self.get_visible_coupon_numbers()
        parsed_in_batch = 0

        for coupon_number in visible_coupons:
            if coupon_number in self.parsed_events:
                continue

            print(f"🎯 Парсим видимую ставку: {coupon_number}")

            try:
                # Получаем информацию о ставке
                bet_info = self.get_bet_info_by_coupon(coupon_number)
                if not bet_info:
                    continue

                # Пропускаем "Не рассчитано"
                if "Не рассчитано" in bet_info.get('result', ''):
                    print(f"⏳ Пропускаем - не рассчитано: {coupon_number}")
                    self.parsed_events.add(coupon_number)
                    continue

                # Обрабатываем проигрыши - исправляем суммы
                if "Проигрыш" in bet_info.get('result', ''):
                    # Если сумма ставки пустая, но есть сумма в выигрыше (для проигрышей)
                    if not bet_info.get('stake_amount') and bet_info.get('win_amount'):
                        # Меняем местами - сумма ставки берется из win_amount, а результат становится отрицательным
                        bet_info['stake_amount'] = bet_info['win_amount']
                        bet_info['win_amount'] = '-' + bet_info['win_amount']
                    elif not bet_info.get('stake_amount'):
                        # Если суммы нет вообще, ставим 330 по умолчанию
                        bet_info['stake_amount'] = '330'
                        bet_info['win_amount'] = '-330'

                # Пытаемся получить детали
                detail_info = None
                if self.expand_bet(coupon_number):
                    detail_info = self.get_expanded_details()

                    # Если это экспресс, получаем список событий
                    if "Экспресс" in bet_info.get('pari_type', ''):
                        express_events = self.get_express_events()
                        if express_events:
                            detail_info['express_events'] = express_events

                    self.close_all_expanded_bets()

                # Сохраняем данные
                if detail_info:
                    combined_info = {**bet_info, **detail_info, 'expanded': True}
                else:
                    combined_info = {**bet_info, 'expanded': False}

                self.data.append(combined_info)
                self.parsed_events.add(coupon_number)
                parsed_in_batch += 1

                print(f"✅ Спарсено: {coupon_number} (всего: {len(self.data)})")

            except Exception as e:
                print(f"❌ Ошибка при парсинге {coupon_number}: {e}")
                continue

        return parsed_in_batch

    def get_bet_info_by_coupon(self, coupon_number):
        """Получает информацию о ставке по номеру купона"""
        try:
            script = f"""
            var coupon = "{coupon_number}";
            var virtualList = document.querySelector('div.virtual-list--FMDYy');
            if (!virtualList) return null;

            var childDivs = virtualList.querySelectorAll('div[style*="top"]');
            for (var i = 0; i < childDivs.length; i++) {{
                var div = childDivs[i];
                if (div.querySelector('.stickyDate--C07hV')) continue;

                var couponElement = div.querySelector('.cellCouponNumber--K_lV2 span');
                if (couponElement && couponElement.textContent.trim() === coupon) {{
                    var timeElem = div.querySelector('.cellDateTime--aAcVV');
                    var typeElem = div.querySelector('.cellPariType--NT1UE .text--Y2SFL');
                    var descElem = div.querySelector('.cellDescription--qMVcZ .text--Y2SFL');
                    var factorElem = div.querySelector('.cellFactor--EzOlj span');
                    var resultElem = div.querySelector('.cellResult--RBrFe');
                    var sumElem = div.querySelector('.cellSum--xyTuh');

                    // Проверяем наличие фрибета
                    var freebetElem = div.querySelector('.cellDescription--qMVcZ .desc--FgM5R');
                    var hasFreebet = freebetElem && freebetElem.textContent.trim() === 'Фрибет';

                    // Извлекаем сумму ставки и выигрыш
                    var stakeAmount = '';
                    var winAmount = '';

                    if (sumElem) {{
                        var grayedElement = sumElem.querySelector('.grayed--i1Uac');
                        var primaryRow = sumElem.querySelector('.sum-row-primary--l0hdi');

                        if (grayedElement) {{
                            stakeAmount = grayedElement.textContent.trim();
                        }}

                        if (primaryRow) {{
                            var primaryText = primaryRow.textContent.trim();
                            if (grayedElement) {{
                                primaryText = primaryText.replace(grayedElement.textContent.trim(), '').trim();
                            }}
                            // Убираем стрелку и лишние пробелы
                            primaryText = primaryText.replace(/\\\\s+/g, ' ').trim();
                            winAmount = primaryText;
                        }}
                    }}

                    // Формируем описание с учетом фрибета
                    var description = descElem ? descElem.textContent.trim() : '';
                    if (hasFreebet) {{
                        description = description + ' (Фрибет)';
                    }}

                    return {{
                        time: timeElem ? timeElem.textContent.trim() : '',
                        pari_type: typeElem ? typeElem.textContent.trim() : '',
                        description: description,
                        factor: factorElem ? factorElem.textContent.trim() : '',
                        result: resultElem ? resultElem.textContent.trim() : '',
                        stake_amount: stakeAmount,
                        win_amount: winAmount,
                        coupon_number: coupon,
                        has_freebet: hasFreebet
                    }};
                }}
            }}
            return null;
            """

            main_info = self.driver.execute_script(script)
            return main_info

        except Exception as e:
            print(f"❌ Ошибка при получении информации для {coupon_number}: {e}")
            return None

    def expand_bet(self, coupon_number):
        """Разворачивает ставку"""
        try:
            script = f"""
            var coupon = "{coupon_number}";
            var virtualList = document.querySelector('div.virtual-list--FMDYy');
            if (!virtualList) return false;

            var childDivs = virtualList.querySelectorAll('div[style*="top"]');
            for (var i = 0; i < childDivs.length; i++) {{
                var div = childDivs[i];
                if (div.querySelector('.stickyDate--C07hV')) continue;

                var couponElement = div.querySelector('.cellCouponNumber--K_lV2 span');
                if (couponElement && couponElement.textContent.trim() === coupon) {{
                    var expander = div.querySelector('.expander--R_AYG');
                    if (expander) {{
                        expander.click();
                        return true;
                    }}
                }}
            }}
            return false;
            """

            result = self.driver.execute_script(script)
            time.sleep(2)  # Ждем загрузки деталей
            return result

        except Exception as e:
            print(f"❌ Ошибка при разворачивании ставки {coupon_number}: {e}")
            return False

    def get_expanded_details(self):
        """Получает детальную информацию из развернутого блока"""
        try:
            script = """
            var detailBlock = document.querySelector('div.data--SaCy0');
            if (!detailBlock) return null;

            var startTimeElem = detailBlock.querySelector('._cell1--QzpZV:not(._header--Rih2b)');
            var eventElem = detailBlock.querySelector('.event-name--Q2Z2Q');
            var pariElem = detailBlock.querySelector('._cell3--DvPpz:not(._header--Rih2b)');
            var factorElem = detailBlock.querySelector('.factor-value--FOM8c');
            var scoreElem = detailBlock.querySelector('._cell5--xC26c:not(._header--Rih2b)');
            var resultElem = detailBlock.querySelector('._cell6--x_CDX:not(._header--Rih2b)');

            return {
                start_time: startTimeElem ? startTimeElem.textContent.trim() : '',
                event: eventElem ? eventElem.textContent.trim() : '',
                pari: pariElem ? pariElem.textContent.trim() : '',
                detail_factor: factorElem ? factorElem.textContent.trim() : '',
                score: scoreElem ? scoreElem.textContent.trim() : '',
                detail_result: resultElem ? resultElem.textContent.trim() : ''
            };
            """

            details = self.driver.execute_script(script)
            return details

        except Exception as e:
            print(f"❌ Ошибка при получении деталей: {e}")
            return None

    def get_express_events(self):
        """Получает список событий в экспрессе"""
        try:
            script = """
            var expressEvents = [];
            var expressBlocks = document.querySelectorAll('div.row--ybiPS._expanded--nyYLU div.data--SaCy0');

            if (expressBlocks.length > 0) {
                var events = expressBlocks[0].querySelectorAll('div.row--ybiPS:not(._header--Rih2b)');

                for (var i = 0; i < events.length; i++) {
                    var event = events[i];
                    var eventName = event.querySelector('.event-name--Q2Z2Q');
                    var pari = event.querySelector('._cell3--DvPpz');
                    var result = event.querySelector('._cell6--x_CDX');

                    if (eventName && pari && result) {
                        expressEvents.push({
                            event: eventName.textContent.trim(),
                            pari: pari.textContent.trim(),
                            result: result.textContent.trim()
                        });
                    }
                }
            }

            return expressEvents;
            """

            events = self.driver.execute_script(script)
            return events
        except Exception as e:
            print(f"❌ Ошибка при получении событий экспресса: {e}")
            return None

    def close_all_expanded_bets(self):
        """Закрывает все развернутые ставки"""
        try:
            script = """
            var expandedBets = document.querySelectorAll('div.row--ybiPS._expanded--nyYLU');
            var closedCount = 0;
            for (var i = 0; i < expandedBets.length; i++) {
                var expander = expandedBets[i].querySelector('.expander--R_AYG');
                if (expander) {
                    expander.click();
                    closedCount++;
                }
            }
            return closedCount;
            """
            closed_count = self.driver.execute_script(script)
            time.sleep(0.5)
            return closed_count > 0
        except Exception as e:
            print(f"❌ Ошибка при закрытии ставок: {e}")
            return False

    def check_if_more_events_available(self):
        """Проверяет, есть ли еще события для загрузки"""
        try:
            script = """
            var scrollBlock = document.querySelector('div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO');
            if (!scrollBlock) return false;

            var currentScroll = scrollBlock.scrollTop;
            var scrollHeight = scrollBlock.scrollHeight;
            var clientHeight = scrollBlock.clientHeight;

            // Если мы близко к концу (осталось меньше 100px)
            return (currentScroll + clientHeight) < (scrollHeight - 100);
            """

            return self.driver.execute_script(script)
        except Exception as e:
            print(f"❌ Ошибка при проверке доступности событий: {e}")
            return False

    def parse_bets(self):
        """Основной метод парсинга с пошаговой прокруткой"""
        print(f"🎯 Начинаем парсинг {self.max_events} самых свежих событий...")

        # Начинаем с самого верха
        self.scroll_to_top()
        time.sleep(3)

        consecutive_empty_scrolls = 0
        max_empty_scrolls = 5

        while len(self.data) < self.max_events and consecutive_empty_scrolls < max_empty_scrolls:
            print(f"\n📊 Прогресс: {len(self.data)}/{self.max_events} событий")

            # Парсим все видимые ставки
            parsed_count = self.parse_visible_bets()

            if parsed_count > 0:
                consecutive_empty_scrolls = 0
                print(f"✅ В этой области спарсено: {parsed_count} событий")
            else:
                consecutive_empty_scrolls += 1
                print(f"⚠️ В видимой области нет новых событий (пустых прокруток: {consecutive_empty_scrolls})")

            # Проверяем, есть ли еще события для загрузки
            if not self.check_if_more_events_available():
                print("📜 Достигнут конец списка событий")
                break

            # Прокручиваем дальше
            if len(self.data) < self.max_events:
                print("🔄 Прокручиваем для загрузки новых событий...")
                if not self.scroll_step_by_step():
                    print("❌ Не удалось прокрутить")
                    break

        print(f"\n✅ Парсинг завершен. Обработано событий: {len(self.data)}")

        if len(self.data) < self.max_events:
            print(f"⚠️ Запрошено {self.max_events}, но найдено только {len(self.data)} событий")

    def save_to_csv(self, filename="fon_bet_data.csv"):
        """Сохранение данных в CSV файл"""
        if not self.data:
            print("❌ Нет данных для сохранения")
            return

        fieldnames = [
            'coupon_number', 'time', 'pari_type', 'description', 'factor', 'result',
            'stake_amount', 'win_amount', 'start_time', 'event', 'pari',
            'detail_factor', 'score', 'detail_result', 'expanded', 'express_events', 'has_freebet'
        ]

        file_exists = os.path.isfile(filename)

        try:
            if file_exists:
                with open(filename, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if 'sum' in first_line and ('stake_amount' not in first_line or 'win_amount' not in first_line):
                        backup_name = filename.replace('.csv', '_backup.csv')
                        os.rename(filename, backup_name)
                        print(f"💾 Создан backup старого файла: {backup_name}")
                        file_exists = False

            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()

                for row in self.data:
                    new_row = {}
                    for field in fieldnames:
                        if field == 'express_events' and field in row:
                            # Форматируем события экспресса в строку
                            events_list = []
                            for event in row[field]:
                                events_list.append(
                                    f"{event.get('event', '')}: {event.get('pari', '')} - {event.get('result', '')}")
                            new_row[field] = '; '.join(events_list)
                        else:
                            new_row[field] = row.get(field, '')
                    writer.writerow(new_row)

            print(f"💾 Данные сохранены в файл: {filename}")
            print(f"📊 Добавлено записей: {len(self.data)}")

        except Exception as e:
            print(f"❌ Ошибка при сохранении в CSV: {e}")

    def display_parsed_data(self):
        """Отображение спарсенных данных в консоли"""
        if not self.data:
            print("❌ Нет данных для отображения")
            return

        print("\n" + "=" * 120)
        print("📋 СПАРСЕННЫЕ ДАННЫЕ (САМЫЕ СВЕЖИЕ):")
        print("=" * 120)

        for i, bet in enumerate(self.data, 1):
            print(f"\n--- Ставка #{i} ---")
            print(f"🎫 Номер пари: {bet.get('coupon_number', 'N/A')}")
            print(f"🕒 Время ставки: {bet.get('time', 'N/A')}")
            print(f"📝 Тип пари: {bet.get('pari_type', 'N/A')}")
            print(f"📄 Описание: {bet.get('description', 'N/A')}")

            # Показываем информацию о фрибете
            if bet.get('has_freebet'):
                print(f"🎁 Фрибет: Да")

            print(f"📈 Коэффициент: {bet.get('factor', 'N/A')}")
            print(f"🎯 Результат: {bet.get('result', 'N/A')}")
            print(f"💰 Сумма ставки: {bet.get('stake_amount', 'N/A')}")
            print(f"💰 Выигрыш: {bet.get('win_amount', 'N/A')}")

            if bet.get('expanded'):
                print(f"⏰ Время начала: {bet.get('start_time', 'N/A')}")
                print(f"🏆 Событие: {bet.get('event', 'N/A')}")
                print(f"🎲 Пари: {bet.get('pari', 'N/A')}")
                print(f"📊 Коэффициент (детали): {bet.get('detail_factor', 'N/A')}")
                print(f"📋 Счет: {bet.get('score', 'N/A')}")
                print(f"✅ Результат (детали): {bet.get('detail_result', 'N/A')}")

                # Показываем события экспресса, если есть
                if 'express_events' in bet and bet['express_events']:
                    print(f"🎪 События экспресса:")
                    for j, event in enumerate(bet['express_events'], 1):
                        print(
                            f"   {j}. {event.get('event', 'N/A')}: {event.get('pari', 'N/A')} - {event.get('result', 'N/A')}")

            print("-" * 50)

        print(f"\n📊 Итого спарсено ставок: {len(self.data)}")