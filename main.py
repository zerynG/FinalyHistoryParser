# main.py (обновленная версия)
from auto import authenticate
from scroll import ScrollBlock
from parser import FonBetParser
from parsing_modes import select_parsing_mode
import time
import getpass


def main():
    # Выполняем авторизацию
    print("🔐 Начинаем авторизацию...")
    driver = authenticate()

    if driver:
        try:
            # Ждем полной загрузки страницы после авторизации
            print("⏳ Ожидаем загрузку страницы...")
            time.sleep(5)

            # Сначала выполняем прокрутку вниз до конца, чтобы загрузились все события
            print("📜 Выполняем прокрутку для загрузки всех ставок...")
            scroll_handler = ScrollBlock(driver)
            if scroll_handler.find_block():
                print("⬇️ Прокручиваем вниз до конца...")
                scroll_handler.scroll_down_gradual()
                time.sleep(2)

                # Возвращаемся на самый верх к самым свежим событиям
                print("⬆️ Возвращаемся к самым свежим событиям...")
                scroll_handler.scroll_to_top()
                time.sleep(2)

            # Инициализируем парсер
            parser = FonBetParser(driver)

            # Выбираем режим парсинга
            mode_selector = select_parsing_mode(driver, parser)

            print("\n✅ Парсинг завершен успешно!")

        except Exception as e:
            print(f"❌ Произошла ошибка: {e}")

        finally:
            # Закрываем браузер
            close = input("🔒 Закрыть браузер? (y/n): ").lower()
            if close == 'y':
                driver.quit()
                print("👋 Браузер закрыт.")
            else:
                print("ℹ️ Браузер остается открытым.")

    else:
        print("❌ Не удалось выполнить авторизацию!")


if __name__ == "__main__":
    main()