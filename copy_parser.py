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
        self.wait = WebDriverWait(driver, 10)
        self.max_events = max_events
        self.parsed_events = set()
        self.data = []

    def refresh_bet_blocks(self):
        """Обновление списка блоков ставок для борьбы с StaleElement"""
        time.sleep(1)
        return self.find_all_bet_blocks()

    def find_all_bet_blocks(self):
        """Поиск ВСЕХ блоков с ставками без фильтрации"""
        try:
            bet_blocks = self.wait.until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR,
                    'div.row--ybiPS'
                ))
            )
            print(f"Найдено всех блоков ставок: {len(bet_blocks)}")
            return bet_blocks
        except TimeoutException:
            print("Не удалось найти блоки ставок")
            return []

    def get_valid_bet_blocks(self):
        """Получение валидных блоков ставок для парсинга с обновлением DOM"""
        all_blocks = self.refresh_bet_blocks()
        valid_blocks = []

        for block in all_blocks:
            try:
                coupon_element = block.find_element(By.CSS_SELECTOR, '.cellCouponNumber--K_lV2 span')
                coupon_number = coupon_element.text.strip()
                if coupon_number and coupon_number not in self.parsed_events:
                    valid_blocks.append(block)
            except StaleElementReferenceException:
                print("🔄 Обнаружен устаревший элемент при фильтрации")
                continue
            except:
                continue

        print(f"Валидных блоков для парсинга: {len(valid_blocks)}")
        return valid_blocks

    def extract_main_bet_info(self, bet_block):
        """Извлечение основной информации о ставке с улучшенной обработкой StaleElement"""
        try:
            # Проверяем, не устарел ли элемент
            bet_block.is_enabled()

            # Время
            time_element = bet_block.find_element(By.CSS_SELECTOR, '.cellDateTime--aAcVV')
            bet_time = time_element.text.strip() if time_element else ""

            # Номер пари
            coupon_element = bet_block.find_element(By.CSS_SELECTOR, '.cellCouponNumber--K_lV2 span')
            coupon_number = coupon_element.text.strip() if coupon_element else ""

            # Тип пари
            pari_type_element = bet_block.find_element(By.CSS_SELECTOR, '.cellPariType--NT1UE .text--Y2SFL')
            pari_type = pari_type_element.text.strip() if pari_type_element else ""

            # Описание
            description_element = bet_block.find_element(By.CSS_SELECTOR, '.cellDescription--qMVcZ .text--Y2SFL')
            description = description_element.text.strip() if description_element else ""

            # Коэффициент
            factor_element = bet_block.find_element(By.CSS_SELECTOR, '.cellFactor--EzOlj span')
            factor = factor_element.text.strip() if factor_element else ""

            # Результат - проверяем на "Не рассчитано"
            result_element = bet_block.find_element(By.CSS_SELECTOR, '.cellResult--RBrFe')
            result = result_element.text.strip() if result_element else ""

            # Пропускаем ставки с результатом "Не рассчитано"
            if "Не рассчитано" in result:
                print(f"⏳ Пропускаем ставку {coupon_number} - результат не рассчитан")
                # Добавляем в parsed_events чтобы больше не обрабатывать
                self.parsed_events.add(coupon_number)
                return None

            # Сумма
            sum_element = bet_block.find_element(By.CSS_SELECTOR, '.cellSum--xyTuh')
            sum_text = sum_element.text.strip() if sum_element else ""

            return {
                'coupon_number': coupon_number,
                'time': bet_time,
                'pari_type': pari_type,
                'description': description,
                'factor': factor,
                'result': result,
                'sum': sum_text,
                'expanded': False
            }
        except StaleElementReferenceException:
            print("❌ Элемент устарел при извлечении информации")
            raise  # Пробрасываем исключение для обработки на верхнем уровне
        except NoSuchElementException as e:
            print(f"❌ Ошибка при извлечении основной информации: {e}")
            return None

    def expand_bet_details(self, coupon_number):
        """Разворачивание деталей ставки по номеру купона"""
        try:
            # Закрываем все другие открытые ставки
            self.close_all_expanded_bets()
            time.sleep(0.5)

            # Находим ставку по номеру купона
            bet_block = self.find_bet_by_coupon(coupon_number)
            if not bet_block:
                print(f"❌ Не удалось найти ставку {coupon_number} для разворачивания")
                return False

            # Прокручиваем к элементу
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", bet_block)
            time.sleep(0.5)

            expander = bet_block.find_element(By.CSS_SELECTOR, '.expander--R_AYG')

            # Кликаем для разворачивания
            self.driver.execute_script("arguments[0].click();", expander)
            time.sleep(2)  # Увеличиваем время ожидания загрузки деталей

            # Проверяем, что ставка развернулась
            try:
                expanded_block = self.wait.until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR,
                        f'div.row--ybiPS._expanded--nyYLU'
                    ))
                )
                return True
            except:
                print(f"❌ Ставка {coupon_number} не развернулась после клика")
                return False

        except Exception as e:
            print(f"❌ Не удалось развернуть детали ставки {coupon_number}: {e}")
            return False

    def find_bet_by_coupon(self, coupon_number):
        """Находит блок ставки по номеру купона"""
        try:
            bet_blocks = self.refresh_bet_blocks()
            for block in bet_blocks:
                try:
                    coupon_element = block.find_element(By.CSS_SELECTOR, '.cellCouponNumber--K_lV2 span')
                    current_coupon = coupon_element.text.strip()
                    if current_coupon == coupon_number:
                        return block
                except StaleElementReferenceException:
                    continue
                except:
                    continue
            return None
        except:
            return None

    def close_all_expanded_bets(self):
        """Закрывает все развернутые ставки"""
        try:
            expanded_bets = self.driver.find_elements(By.CSS_SELECTOR, 'div.row--ybiPS._expanded--nyYLU')
            for bet in expanded_bets:
                try:
                    expander = bet.find_element(By.CSS_SELECTOR, '.expander--R_AYG')
                    self.driver.execute_script("arguments[0].click();", expander)
                    time.sleep(0.2)
                except:
                    continue
            time.sleep(0.5)
        except:
            pass

    def extract_expanded_details(self, coupon_number):
        """Извлечение детальной информации из развернутого блока"""
        try:
            # Ждем появления развернутого блока
            detail_block = self.wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    'div.data--SaCy0'
                ))
            )

            event_data = {}

            # Время начала
            try:
                start_time_element = detail_block.find_element(By.CSS_SELECTOR, '._cell1--QzpZV:not(._header--Rih2b)')
                event_data['start_time'] = start_time_element.text.strip()
            except NoSuchElementException:
                event_data['start_time'] = ""

            # Событие
            try:
                event_element = detail_block.find_element(By.CSS_SELECTOR, '.event-name--Q2Z2Q')
                event_data['event'] = event_element.text.strip()
            except NoSuchElementException:
                event_data['event'] = ""

            # Пари
            try:
                pari_element = detail_block.find_element(By.CSS_SELECTOR, '._cell3--DvPpz:not(._header--Rih2b)')
                event_data['pari'] = pari_element.text.strip()
            except NoSuchElementException:
                event_data['pari'] = ""

            # Коэффициент из деталей
            try:
                detail_factor_element = detail_block.find_element(By.CSS_SELECTOR, '.factor-value--FOM8c')
                event_data['detail_factor'] = detail_factor_element.text.strip()
            except NoSuchElementException:
                event_data['detail_factor'] = ""

            # Счет
            try:
                score_element = detail_block.find_element(By.CSS_SELECTOR, '._cell5--xC26c:not(._header--Rih2b)')
                event_data['score'] = score_element.text.strip()
            except NoSuchElementException:
                event_data['score'] = ""

            # Результат из деталей
            try:
                detail_result_element = detail_block.find_element(By.CSS_SELECTOR,
                                                                  '._cell6--x_CDX:not(._header--Rih2b)')
                event_data['detail_result'] = detail_result_element.text.strip()
            except NoSuchElementException:
                event_data['detail_result'] = ""

            event_data['coupon_number'] = coupon_number
            event_data['expanded'] = True

            return event_data

        except TimeoutException:
            print(f"⏳ Не удалось найти детали для ставки {coupon_number}")
            return None
        except Exception as e:
            print(f"❌ Ошибка при извлечении деталей для {coupon_number}: {e}")
            return None

    def scroll_to_top(self):
        """Прокрутка на самый верх"""
        try:
            scroll_block = self.driver.find_element(By.CSS_SELECTOR,
                                                    'div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO')
            self.driver.execute_script("arguments[0].scrollTop = 0;", scroll_block)
            time.sleep(2)
            print("✅ Прокрутка на верх завершена")
        except Exception as e:
            print(f"❌ Ошибка при прокрутке на верх: {e}")

    def load_more_events(self):
        """Загрузка дополнительных событий через прокрутку"""
        try:
            scroll_block = self.driver.find_element(By.CSS_SELECTOR,
                                                    'div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO')

            # Получаем текущее состояние
            current_scroll = self.driver.execute_script("return arguments[0].scrollTop", scroll_block)
            scroll_height = self.driver.execute_script("return arguments[0].scrollHeight", scroll_block)
            client_height = self.driver.execute_script("return arguments[0].clientHeight", scroll_block)

            # Если мы уже внизу, больше грузить нечего
            if current_scroll + client_height >= scroll_height - 100:
                print("📜 Достигнут конец списка, новых событий нет")
                return False

            # Прокручиваем вниз для загрузки новых событий
            self.driver.execute_script(f"arguments[0].scrollTop = {current_scroll + 1200};", scroll_block)
            time.sleep(3)  # Увеличиваем время ожидания загрузки

            # Проверяем, загрузились ли новые события
            new_scroll_height = self.driver.execute_script("return arguments[0].scrollHeight", scroll_block)
            if new_scroll_height > scroll_height:
                print("🔄 Загружены новые события")
                return True
            else:
                print("📜 Новых событий не загружено")
                return False

        except Exception as e:
            print(f"⚠️ Ошибка при загрузке новых событий: {e}")
            return False

    def parse_bets(self):
        """Основной метод парсинга ставок с улучшенной обработкой StaleElement"""
        print(f"🎯 Начинаем парсинг {self.max_events} самых свежих событий...")

        # Сначала прокручиваем на самый верх
        self.scroll_to_top()
        time.sleep(2)

        parsed_count = 0
        load_attempts = 0
        max_load_attempts = 3  # Уменьшаем количество попыток загрузки

        while parsed_count < self.max_events and load_attempts < max_load_attempts:
            print(f"\n🔍 Поиск ставок (попытка загрузки {load_attempts + 1})...")

            # Получаем все доступные блоки ставок
            bet_blocks = self.get_valid_bet_blocks()

            if not bet_blocks:
                print("❌ Не найдено ставок для парсинга")
                if self.load_more_events():
                    load_attempts += 1
                    continue
                else:
                    break

            print(f"📋 Найдено {len(bet_blocks)} ставок для обработки")

            # Обрабатываем ставки по порядку (сверху вниз - самые свежие)
            for i, bet_block in enumerate(bet_blocks):
                if parsed_count >= self.max_events:
                    break

                try:
                    print(f"\n📝 Обрабатываем ставку {parsed_count + 1}/{self.max_events}...")

                    # Извлекаем основную информацию
                    main_info = self.extract_main_bet_info(bet_block)
                    if not main_info:
                        continue

                    print(f"✅ Найдена новая ставка: {main_info['coupon_number']}")

                    # Разворачиваем детали по номеру купона (более стабильный способ)
                    if self.expand_bet_details(main_info['coupon_number']):
                        # Извлекаем детальную информацию
                        detail_info = self.extract_expanded_details(main_info['coupon_number'])

                        if detail_info:
                            # Объединяем основную и детальную информацию
                            combined_info = {**main_info, **detail_info}
                            self.data.append(combined_info)
                            self.parsed_events.add(main_info['coupon_number'])
                            parsed_count += 1
                            print(
                                f"🎉 Парсинг завершен для ставки {main_info['coupon_number']} ({parsed_count}/{self.max_events})")
                        else:
                            print(f"⚠️ Не удалось извлечь детали для {main_info['coupon_number']}")
                            # Сохраняем хотя бы основную информацию
                            self.data.append(main_info)
                            self.parsed_events.add(main_info['coupon_number'])
                            parsed_count += 1
                    else:
                        print(f"⚠️ Не удалось развернуть детали для {main_info['coupon_number']}")
                        # Сохраняем хотя бы основную информацию
                        self.data.append(main_info)
                        self.parsed_events.add(main_info['coupon_number'])
                        parsed_count += 1

                    # Закрываем ставку после парсинга
                    self.close_all_expanded_bets()
                    time.sleep(0.5)

                except StaleElementReferenceException:
                    print("🔄 Элемент устарел, обновляем список и продолжаем...")
                    # Прерываем текущую итерацию и обновляем список
                    break
                except Exception as e:
                    print(f"❌ Ошибка при парсинге блока: {e}")
                    continue

            # Если обработали все доступные блоки, но нужно еще событий
            if parsed_count < self.max_events:
                print(f"\n📜 Нужно больше событий ({parsed_count}/{self.max_events}), загружаем...")
                if self.load_more_events():
                    load_attempts += 1
                    # Даем больше времени на загрузку новых событий
                    time.sleep(3)
                else:
                    print("📜 Больше событий загрузить не удалось")
                    break

        print(f"\n✅ Парсинг завершен. Обработано событий: {len(self.data)}")

    def save_to_csv(self, filename="fon_bet_data2.csv"):
        """Сохранение данных в CSV файл"""
        if not self.data:
            print("❌ Нет данных для сохранения")
            return

        # Определяем поля для CSV
        fieldnames = [
            'coupon_number', 'time', 'pari_type', 'description', 'factor', 'result', 'sum',
            'start_time', 'event', 'pari', 'detail_factor', 'score', 'detail_result', 'expanded'
        ]

        file_exists = os.path.isfile(filename)

        try:
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                if not file_exists:
                    writer.writeheader()

                for row in self.data:
                    writer.writerow(row)

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
            print(f"📈 Коэффициент: {bet.get('factor', 'N/A')}")
            print(f"🎯 Результат: {bet.get('result', 'N/A')}")
            print(f"💰 Сумма: {bet.get('sum', 'N/A')}")

            if bet.get('expanded'):
                print(f"⏰ Время начала: {bet.get('start_time', 'N/A')}")
                print(f"🏆 Событие: {bet.get('event', 'N/A')}")
                print(f"🎲 Пари: {bet.get('pari', 'N/A')}")
                print(f"📊 Коэффициент (детали): {bet.get('detail_factor', 'N/A')}")
                print(f"📋 Счет: {bet.get('score', 'N/A')}")
                print(f"✅ Результат (детали): {bet.get('detail_result', 'N/A')}")