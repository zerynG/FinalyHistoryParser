# scroll.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


class ScrollBlock:
    def __init__(self, driver):
        self.driver = driver
        self.scroll_block = None
        self.scroll_step = 500
        self.max_scroll_attempts = 50
        self.scroll_delay = 0.5

    def find_block(self):
        try:
            self.scroll_block = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    'div.scroll-area__view-port__default--J1yYl._vertical-overflow--MM_JO'
                ))
            )
            print("Блок для прокрутки найден")
            return True
        except Exception as e:
            print(f"Ошибка при поиске блока прокрутки: {e}")
            return False

    def scroll_to_top(self):
        """Прокрутка на самый верх"""
        if not self.scroll_block:
            return False

        try:
            self.driver.execute_script("arguments[0].scrollTop = 0;", self.scroll_block)
            time.sleep(1)
            print("Прокрутка на верх завершена")
            return True
        except Exception as e:
            print(f"Ошибка при прокрутке на верх: {e}")
            return False

    def scroll_down_gradual(self):
        """Постепенная прокрутка вниз для загрузки контента"""
        if not self.scroll_block:
            return False

        try:
            scroll_attempts = 0

            while scroll_attempts < self.max_scroll_attempts:
                current_position = self.driver.execute_script(
                    "return arguments[0].scrollTop", self.scroll_block
                )

                # Прокручиваем вниз
                self.driver.execute_script(
                    f"arguments[0].scrollTop += {self.scroll_step}",
                    self.scroll_block
                )

                time.sleep(self.scroll_delay)

                new_position = self.driver.execute_script(
                    "return arguments[0].scrollTop", self.scroll_block
                )

                # Проверяем, достигли ли мы конца
                scroll_height = self.driver.execute_script(
                    "return arguments[0].scrollHeight", self.scroll_block
                )
                client_height = self.driver.execute_script(
                    "return arguments[0].clientHeight", self.scroll_block
                )

                if new_position + client_height >= scroll_height:
                    print("Достигнут конец страницы")
                    break

                # Если позиция не изменилась, возможно достигнут конец
                if new_position == current_position:
                    print("Прокрутка завершена")
                    break

                scroll_attempts += 1

                if scroll_attempts % 10 == 0:
                    progress = (new_position / (scroll_height - client_height)) * 100
                    print(f"Прогресс прокрутки: {progress:.1f}%")

            return True

        except Exception as e:
            print(f"Ошибка при прокрутке: {e}")
            return False