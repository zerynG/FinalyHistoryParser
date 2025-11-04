import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import os

# Настройка страницы
st.set_page_config(page_title="Анализ ставок FonBet", layout="wide")
st.title("📊 Анализ ставок FonBet")


# Загрузка данных (только чтение)
@st.cache_data
def load_data():
    try:
        # Проверяем существование файла
        if not os.path.exists('fon_bet_data2.csv'):
            st.error("Файл 'fon_bet_data2.csv' не найден!")
            return pd.DataFrame()

        # Читаем файл в режиме только для чтения
        data = pd.read_csv('fon_bet_data2.csv')

        # Создаем полную копию для работы
        df = data.copy()

        # Сохраняем информацию о исходном файле
        original_size = os.path.getsize('fon_bet_data2.csv')
        original_mod_time = os.path.getmtime('fon_bet_data2.csv')

        st.sidebar.success(f"✅ Файл загружен ({len(df)} записей)")
        st.sidebar.info(f"📁 Размер: {original_size} байт")
        st.sidebar.info(f"🕐 Изменен: {datetime.fromtimestamp(original_mod_time).strftime('%d.%m.%Y %H:%M')}")

        # Преобразование даты
        df['start_time'] = pd.to_datetime(df['start_time'], format='%d.%m.%Y %H:%M', errors='coerce')

        # Очистка числовых колонок (работаем только с копией!)
        df['win_amount'] = df['win_amount'].fillna('0').astype(str)
        df['win_amount'] = df['win_amount'].str.replace(' ', '').str.replace(' ', '').astype(float)

        df['stake_amount'] = df['stake_amount'].fillna('0').astype(str)
        df['stake_amount'] = df['stake_amount'].str.replace(' ', '').str.replace(' ', '').astype(float)

        # ДОБАВЛЯЕМ КОЛОНКУ ДЛЯ ПРИБЫЛИ/УБЫТКА КАЖДОЙ СТАВКИ
        df['profit_loss'] = df['win_amount'] - df['stake_amount']

        return df

    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {e}")
        return pd.DataFrame()


# Загружаем данные
df = load_data()

if not df.empty:
    # Сайдбар с фильтрами
    st.sidebar.header("Фильтры")

    # Выбор временного периода
    min_date = df['start_time'].min().date()
    max_date = df['start_time'].max().date()

    date_range = st.sidebar.date_input(
        "Выберите период",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        filtered_df = df[
            (df['start_time'].dt.date >= start_date) &
            (df['start_time'].dt.date <= end_date)
            ]
    else:
        filtered_df = df

    # ОСНОВНЫЕ МЕТРИКИ НА ГЛАВНОЙ СТРАНИЦЕ
    st.header("📈 Основные показатели")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_bets = len(filtered_df)
        st.metric("Всего ставок", total_bets)

    with col2:
        total_stake = filtered_df['stake_amount'].sum()
        st.metric("Общая сумма ставок", f"{total_stake:,.0f} ₽")

    with col3:
        total_win = filtered_df[filtered_df['result'] == 'Выигрыш']['win_amount'].sum()
        st.metric("Общий выигрыш", f"{total_win:,.0f} ₽")

    with col4:
        # ПРАВИЛЬНЫЙ РАСЧЕТ ЧИСТОЙ ПРИБЫЛИ: сумма всех profit_loss
        net_profit = filtered_df['profit_loss'].sum()
        profit_color = "normal" if net_profit >= 0 else "inverse"
        st.metric("Чистая прибыль/убыток", f"{net_profit:,.0f} ₽",
                  delta_color=profit_color)

    # НОВЫЕ ПОКАЗАТЕЛИ: ОБОРОТ И ЧИСТАЯ ПРИБЫЛЬ ЗА ВСЕ ВРЕМЯ
    st.subheader("💰 Общие финансовые показатели")

    col1, col2 = st.columns(2)

    with col1:
        # Общий оборот за все время (сумма всех ставок)
        total_turnover = filtered_df['stake_amount'].sum()
        st.metric("Общий оборот за период", f"{total_turnover:,.0f} ₽")

    with col2:
        # Чистая прибыль/убыток за все время (правильный расчет)
        total_net_profit = filtered_df['profit_loss'].sum()
        profit_label = "Чистая прибыль" if total_net_profit >= 0 else "Чистый убыток"
        st.metric(profit_label, f"{total_net_profit:,.0f} ₽",
                  delta_color="normal" if total_net_profit >= 0 else "inverse")

    # ТАБЛИЦА С ЕЖЕДНЕВНОЙ СТАТИСТИКОЙ
    st.subheader("📊 Ежедневная статистика")

    # ПРАВИЛЬНАЯ ЛОГИКА ВЫЧИСЛЕНИЯ ПРИБЫЛИ/УБЫТКА
    # Прибыль/убыток = сумма всех (win_amount - stake_amount) за день
    daily_stats = filtered_df.groupby(filtered_df['start_time'].dt.date).agg({
        'stake_amount': ['sum', 'count'],  # оборот и количество ставок
        'profit_loss': 'sum',  # сумма всех прибылей/убытков
        'result': lambda x: (x == 'Выигрыш').sum()  # количество выигрышных ставок
    }).reset_index()

    # Упрощаем названия колонок
    daily_stats.columns = ['date', 'daily_turnover', 'bets_count', 'daily_net_profit', 'win_bets_count']

    # Рассчитываем винрейт за день
    daily_stats['daily_winrate'] = (daily_stats['win_bets_count'] / daily_stats['bets_count'] * 100).round(1)

    # Сортируем по дате (от новых к старым)
    daily_stats = daily_stats.sort_values('date', ascending=False)

    # Форматируем дату для отображения
    daily_stats['date_str'] = daily_stats['date'].apply(lambda x: x.strftime('%d.%m.%Y'))

    # Создаем красивую таблицу для отображения
    display_table = daily_stats[
        ['date_str', 'daily_net_profit', 'bets_count', 'daily_turnover', 'daily_winrate']].copy()
    display_table.columns = ['Дата', 'Прибыль/Убыток (₽)', 'Кол-во ставок', 'Оборот (₽)', 'Winrate (%)']

    # Форматируем числа
    display_table['Прибыль/Убыток (₽)'] = display_table['Прибыль/Убыток (₽)'].apply(lambda x: f"{x:,.0f} ₽")
    display_table['Оборот (₽)'] = display_table['Оборот (₽)'].apply(lambda x: f"{x:,.0f} ₽")
    display_table['Winrate (%)'] = display_table['Winrate (%)'].apply(lambda x: f"{x}%")

    # Отображаем таблицу
    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True
    )

    # Разделы для дополнительной аналитики
    tab1, tab2, tab3 = st.tabs(["📈 Графики", "🎯 Детальная аналитика", "📋 Все ставки"])

    with tab1:
        st.header("📈 Графики аналитики")

        if len(daily_stats) > 1:
            # Сортируем по дате для графиков
            daily_stats_sorted = daily_stats.sort_values('date')

            # ГРАФИК 1: ЕЖЕДНЕВНАЯ ПРИБЫЛЬ/УБЫТОК
            st.subheader("Ежедневная прибыль/убыток")

            fig1, ax1 = plt.subplots(figsize=(12, 6))

            # Создаем столбчатую диаграмму с разными цветами для прибыли и убытка
            colors = ['#4CAF50' if x >= 0 else '#F44336' for x in daily_stats_sorted['daily_net_profit']]
            bars = ax1.bar(daily_stats_sorted['date_str'], daily_stats_sorted['daily_net_profit'],
                           color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

            ax1.set_xlabel('Дата')
            ax1.set_ylabel('Прибыль/Убыток (₽)')
            ax1.set_title('Ежедневная прибыль/убыток')
            ax1.grid(True, alpha=0.3)
            plt.xticks(rotation=45)

            # Добавляем значения на столбцы
            for bar in bars:
                height = bar.get_height()
                if height != 0:  # Не показываем 0 значения
                    ax1.text(bar.get_x() + bar.get_width() / 2., height,
                             f'{height:,.0f}',
                             ha='center', va='bottom' if height > 0 else 'top',
                             fontsize=8, fontweight='bold')

            # Добавляем линию нуля
            ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3)

            plt.tight_layout()
            st.pyplot(fig1)

            # ГРАФИК 2: ЕЖЕДНЕВНЫЙ WINRATE
            st.subheader("Ежедневный Winrate")

            fig2, ax2 = plt.subplots(figsize=(12, 6))

            # Линия винрейта
            line = ax2.plot(daily_stats_sorted['date_str'], daily_stats_sorted['daily_winrate'],
                            marker='o', linewidth=2, markersize=6, color='#2196F3', label='Winrate')

            ax2.set_xlabel('Дата')
            ax2.set_ylabel('Winrate (%)')
            ax2.set_title('Ежедневный Winrate')
            ax2.grid(True, alpha=0.3)
            ax2.set_ylim(0, 100)  # Winrate от 0% до 100%

            # Добавляем значения на точки
            for i, (date, winrate) in enumerate(
                    zip(daily_stats_sorted['date_str'], daily_stats_sorted['daily_winrate'])):
                ax2.annotate(f'{winrate}%',
                             (date, winrate),
                             textcoords="offset points",
                             xytext=(0, 10),
                             ha='center',
                             fontsize=8,
                             fontweight='bold')

            # Линия среднего винрейта
            avg_winrate = daily_stats_sorted['daily_winrate'].mean()
            ax2.axhline(y=avg_winrate, color='red', linestyle='--', alpha=0.7,
                        label=f'Средний: {avg_winrate:.1f}%')

            ax2.legend()
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig2)

            # ГРАФИК 3: СОВМЕЩЕННЫЙ ГРАФИК (ПРИБЫЛЬ И WINRATE)
            st.subheader("Совмещенный анализ: Прибыль и Winrate")

            fig3, ax3 = plt.subplots(figsize=(12, 6))

            # Две оси Y
            ax3_profit = ax3
            ax3_winrate = ax3.twinx()

            # Столбцы прибыли/убытка
            colors = ['#4CAF50' if x >= 0 else '#F44336' for x in daily_stats_sorted['daily_net_profit']]
            bars = ax3_profit.bar(daily_stats_sorted['date_str'], daily_stats_sorted['daily_net_profit'],
                                  color=colors, alpha=0.6, label='Прибыль/Убыток')

            # Линия винрейта
            line = ax3_winrate.plot(daily_stats_sorted['date_str'], daily_stats_sorted['daily_winrate'],
                                    color='#FF9800', linewidth=3, marker='s', markersize=4,
                                    label='Winrate')

            # Настройки осей
            ax3_profit.set_xlabel('Дата')
            ax3_profit.set_ylabel('Прибыль/Убыток (₽)', color='black')
            ax3_winrate.set_ylabel('Winrate (%)', color='#FF9800')

            ax3_profit.tick_params(axis='y', labelcolor='black')
            ax3_winrate.tick_params(axis='y', labelcolor='#FF9800')

            ax3_profit.set_title('Совмещенный анализ: Прибыль/Убыток и Winrate')
            ax3_profit.grid(True, alpha=0.3)

            # Линия нуля для прибыли
            ax3_profit.axhline(y=0, color='black', linestyle='-', alpha=0.3)

            # Объединяем легенды
            lines1, labels1 = ax3_profit.get_legend_handles_labels()
            lines2, labels2 = ax3_winrate.get_legend_handles_labels()
            ax3_profit.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig3)

        else:
            st.info("Недостаточно данных для построения графиков")

    with tab2:
        st.header("🎯 Детальная аналитика")

        # Статистика по периодам
        current_date = datetime.now().date()

        # Сегодня
        today_df = filtered_df[filtered_df['start_time'].dt.date == current_date]
        today_profit = today_df['profit_loss'].sum()
        today_stake = today_df['stake_amount'].sum()

        # Неделя (последние 7 дней)
        week_ago = current_date - timedelta(days=7)
        week_df = filtered_df[filtered_df['start_time'].dt.date >= week_ago]
        week_profit = week_df['profit_loss'].sum()
        week_stake = week_df['stake_amount'].sum()

        # Месяц (последние 30 дней)
        month_ago = current_date - timedelta(days=30)
        month_df = filtered_df[filtered_df['start_time'].dt.date >= month_ago]
        month_profit = month_df['profit_loss'].sum()
        month_stake = month_df['stake_amount'].sum()

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("За сегодня",
                      f"{today_profit:,.0f} ₽",
                      delta=f"Оборот: {today_stake:,.0f} ₽")

        with col2:
            st.metric("За неделю",
                      f"{week_profit:,.0f} ₽",
                      delta=f"Оборот: {week_stake:,.0f} ₽")

        with col3:
            st.metric("За месяц",
                      f"{month_profit:,.0f} ₽",
                      delta=f"Оборот: {month_stake:,.0f} ₽")

        # Winrate анализ
        st.subheader("Анализ эффективности")

        total_bets_count = len(filtered_df)
        win_bets = len(filtered_df[filtered_df['result'] == 'Выигрыш'])

        if total_bets_count > 0:
            winrate = (win_bets / total_bets_count) * 100

            col1, col2 = st.columns(2)

            with col1:
                st.metric("Общий Winrate", f"{winrate:.1f}%")
                st.metric("Выигрышных ставок", win_bets)

            with col2:
                st.metric("Общее количество ставок", total_bets_count)
                avg_profit_per_bet = total_net_profit / total_bets_count if total_bets_count > 0 else 0
                st.metric("Средняя прибыль на ставку", f"{avg_profit_per_bet:,.0f} ₽")

    with tab3:
        st.header("📋 Все ставки за период")
        # Добавляем колонку прибыли/убытка в отображаемую таблицу
        display_columns = ['start_time', 'event', 'pari', 'result', 'stake_amount', 'win_amount', 'profit_loss']
        st.dataframe(
            filtered_df[display_columns].sort_values('start_time', ascending=False),
            use_container_width=True
        )

# Информация о защите файла
st.sidebar.header("🔒 Защита данных")
st.sidebar.info("Исходный CSV файл защищен от изменений")
st.sidebar.info("Все вычисления производятся на копии данных")