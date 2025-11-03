from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import time
import getpass


class AuthParser:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.login_url = "https://fon.bet/account/history/bets"
        self.phone_number = "79164322517"
        self.wait_timeout = 10

    def setup_driver(self):
        """Настройка веб-драйвера с автоматической установкой ChromeDriver"""
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--start-maximized')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, self.wait_timeout)

    def login(self, password):
        """Выполнение авторизации"""
        try:
            print("Переходим на страницу авторизации...")
            self.driver.get(self.login_url)

            print("Ожидаем появление поля логина...")
            login_field = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="login"]'))
            )

            print("Вводим номер телефона...")
            login_field.clear()
            login_field.send_keys(self.phone_number)

            print("Находим поле пароля...")
            password_field = self.driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')

            print("Вводим пароль...")
            password_field.clear()
            password_field.send_keys(password)

            print("Нажимаем кнопку 'Войти'...")
            login_button = self.driver.find_element(
                By.CSS_SELECTOR,
                'span.button--_ckCX._primary--xaCqa._sizeL--cOYoD._hasText--a86Tm._interactive--hyuU0'
            )
            login_button.click()

            print("Ожидаем завершение авторизации...")
            time.sleep(5)

            # Проверяем, успешна ли авторизация
            current_url = self.driver.current_url
            if "history/bets" in current_url:
                print("Авторизация выполнена успешно!")
                return True
            else:
                print("Возможно, возникла проблема с авторизацией")
                return False

        except Exception as e:
            print(f"Ошибка при авторизации: {e}")
            return False

    def get_driver(self):
        """Возвращает экземпляр драйвера для использования в других модулях"""
        return self.driver

    def close(self):
        """Закрытие браузера"""
        if self.driver:
            self.driver.quit()


def authenticate():
    """Функция авторизации для использования в других модулях"""
    password = getpass.getpass("Введите пароль для авторизации: ")

    parser = AuthParser()

    try:
        parser.setup_driver()
        success = parser.login(password)

        if success:
            print("Авторизация успешна!")
            return parser.get_driver()
        else:
            print("Ошибка авторизации!")
            parser.close()
            return None

    except Exception as e:
        print(f"Произошла ошибка: {e}")
        parser.close()
        return None


if __name__ == "__main__":
    driver = authenticate()

    if driver:
        print(f"Текущий URL: {driver.current_url}")
        print("Драйвер активен и готов к использованию.")