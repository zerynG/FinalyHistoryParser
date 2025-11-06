import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import io

# Настройка страницы
st.set_page_config(
    page_title="Анализ ставок FonBet",
    page_icon="📊",
    layout="wide"
)

# Заголовок
st.title("📊 Анализ ставок FonBet")
st.markdown("---")


# Функция для очистки числовых значений
def clean_numeric_value(value):
    if pd.isna(value) or value == '':
        return 0.0
    # Преобразуем в строку и убираем нестандартные символы
    str_value = str(value).strip()
    # Заменяем неразрывные пробелы и обычные пробелы
    str_value = str_value.replace('\xa0', '').replace(' ', '')
    # Заменяем запятые на точки для десятичных чисел
    str_value = str_value.replace(',', '.')

    try:
        return float(str_value)
    except ValueError:
        return 0.0


# Функция для загрузки и обработки данных
@st.cache_data
def load_data():
    try:
        # Читаем CSV файл
        df = pd.read_csv('fon_bet_data2.csv')

        # Преобразуем даты
        df['start_time'] = pd.to_datetime(df['start_time'], format='%d.%m.%Y %H:%M', errors='coerce')
        df['date'] = df['start_time'].dt.date

        # Очищаем числовые колонки
        df['stake_amount'] = df['stake_amount'].apply(clean_numeric_value)
        df['win_amount'] = df['win_amount'].apply(clean_numeric_value)

        # Рассчитываем чистую прибыль/убыль для каждого события
        def calculate_net_profit(row):
            result = str(row['result']).strip()

            if result == 'Выигрыш':
                return row['win_amount'] - row['stake_amount']
            elif result == 'Проигрыш':
                return -row['stake_amount']  # Для проигрыша возвращаем отрицательную сумму ставки
            elif result == 'Продано':
                return row['win_amount'] - row['stake_amount']
            elif result == 'Возврат':
                return 0
            else:
                return 0

        df['net_profit'] = df.apply(calculate_net_profit, axis=1)

        return df

    except Exception as e:
        st.error(f"Ошибка при загрузке данных: {str(e)}")
        return None


# Загружаем данные
df = load_data()

if df is not None:
    # Боковая панель с фильтрами
    st.sidebar.header("🔍 Фильтры")

    # Фильтр по дате
    min_date = df['date'].min()
    max_date = df['date'].max()
    date_range = st.sidebar.date_input(
        "Диапазон дат",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )

    if len(date_range) == 2:
        start_date, end_date = date_range
        df_filtered = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
    else:
        df_filtered = df

    # Фильтр по типу пари
    pari_types = df_filtered['pari_type'].unique()
    selected_types = st.sidebar.multiselect(
        "Тип пари",
        options=pari_types,
        default=pari_types
    )

    if selected_types:
        df_filtered = df_filtered[df_filtered['pari_type'].isin(selected_types)]

    # Фильтр по результату
    results = df_filtered['result'].unique()
    selected_results = st.sidebar.multiselect(
        "Результат",
        options=results,
        default=results
    )

    if selected_results:
        df_filtered = df_filtered[df_filtered['result'].isin(selected_results)]

    # Основная информация
    st.header("📈 Общая статистика")

    col1, col2, col3, col4 = st.columns(4)

    total_events = len(df_filtered)
    total_turnover = df_filtered['stake_amount'].sum()
    total_net_profit = df_filtered['net_profit'].sum()

    winning_events = len(df_filtered[df_filtered['result'] == 'Выигрыш'])
    win_rate = (winning_events / total_events * 100) if total_events > 0 else 0

    with col1:
        st.metric(
            label="Всего событий",
            value=f"{total_events:,}",
            delta=None
        )

    with col2:
        st.metric(
            label="Общий оборот",
            value=f"{total_turnover:,.0f} ₽",
            delta=None
        )

    with col3:
        profit_color = "normal"
        delta_color = "normal"
        if total_net_profit > 0:
            profit_color = "normal"
            delta_color = "normal"
        elif total_net_profit < 0:
            profit_color = "inverse"
            delta_color = "inverse"

        st.metric(
            label="Чистая прибыль/убыль",
            value=f"{total_net_profit:,.0f} ₽",
            delta=f"{total_net_profit:,.0f} ₽",
            delta_color=delta_color
        )

    with col4:
        st.metric(
            label="Винрейт",
            value=f"{win_rate:.1f}%",
            delta=None
        )

    st.markdown("---")

    # Подневная статистика
    st.header("📅 Подневная статистика")

    # Группируем по дням и сортируем по убыванию даты (свежие сверху)
    daily_stats = df_filtered.groupby('date').agg({
        'net_profit': 'sum',
        'stake_amount': 'sum',
        'coupon_number': 'count',
        'result': lambda x: (x == 'Выигрыш').sum()
    }).reset_index()

    daily_stats.columns = ['Дата', 'Чистая прибыль', 'Оборот', 'Кол-во ставок', 'Выигрышных ставок']
    daily_stats['Винрейт %'] = (daily_stats['Выигрышных ставок'] / daily_stats['Кол-во ставок'] * 100).round(1)

    # Сортируем по дате в порядке убывания (свежие сверху)
    daily_stats = daily_stats.sort_values('Дата', ascending=False)

    # Отображаем таблицу
    st.dataframe(
        daily_stats.style.format({
            'Чистая прибыль': '{:,.0f} ₽',
            'Оборот': '{:,.0f} ₽',
            'Кол-во ставок': '{:,.0f}',
            'Выигрышных ставок': '{:,.0f}',
            'Винрейт %': '{:.1f}%'
        }),
        use_container_width=True,
        height=400
    )

    st.markdown("---")

    # Графики с новым стилем
    st.header("📊 Графики аналитики")

    if len(daily_stats) > 0:
        # Сортируем по дате для графиков
        daily_stats_sorted = daily_stats.sort_values('Дата')
        daily_stats_sorted['Дата_стр'] = daily_stats_sorted['Дата'].apply(lambda x: x.strftime('%d.%m.%Y'))

        # ГРАФИК 1: ЕЖЕДНЕВНАЯ ПРИБЫЛЬ/УБЫТОК (стиль из вашего кода)
        st.subheader("Ежедневная прибыль/убыток")

        fig1, ax1 = plt.subplots(figsize=(10, 5))  # Уменьшенный размер

        # Создаем столбчатую диаграмму с разными цветами для прибыли и убытка
        colors = ['#4CAF50' if x >= 0 else '#F44336' for x in daily_stats_sorted['Чистая прибыль']]
        bars = ax1.bar(daily_stats_sorted['Дата_стр'], daily_stats_sorted['Чистая прибыль'],
                       color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

        ax1.set_xlabel('Дата', fontsize=10)
        ax1.set_ylabel('Прибыль/Убыток (₽)', fontsize=10)
        ax1.set_title('Ежедневная прибыль/убыток', fontsize=12, fontweight='bold')
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis='x', rotation=45, labelsize=8)
        ax1.tick_params(axis='y', labelsize=8)

        # Добавляем значения на столбцы
        for bar in bars:
            height = bar.get_height()
            if height != 0:  # Не показываем 0 значения
                ax1.text(bar.get_x() + bar.get_width() / 2., height,
                         f'{height:,.0f}',
                         ha='center', va='bottom' if height > 0 else 'top',
                         fontsize=7, fontweight='bold')

        # Добавляем линию нуля
        ax1.axhline(y=0, color='black', linestyle='-', alpha=0.3)

        plt.tight_layout()
        st.pyplot(fig1)

        # ГРАФИК 2: ЕЖЕДНЕВНЫЙ WINRATE (стиль из вашего кода)
        st.subheader("Ежедневный Winrate")

        fig2, ax2 = plt.subplots(figsize=(10, 5))  # Уменьшенный размер

        # Линия винрейта
        line = ax2.plot(daily_stats_sorted['Дата_стр'], daily_stats_sorted['Винрейт %'],
                        marker='o', linewidth=2, markersize=4, color='#2196F3', label='Winrate')

        ax2.set_xlabel('Дата', fontsize=10)
        ax2.set_ylabel('Winrate (%)', fontsize=10)
        ax2.set_title('Ежедневный Winrate', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        ax2.set_ylim(0, 100)  # Winrate от 0% до 100%
        ax2.tick_params(axis='x', rotation=45, labelsize=8)
        ax2.tick_params(axis='y', labelsize=8)

        # Добавляем значения на точки
        for i, (date, winrate) in enumerate(zip(daily_stats_sorted['Дата_стр'], daily_stats_sorted['Винрейт %'])):
            ax2.annotate(f'{winrate}%',
                         (date, winrate),
                         textcoords="offset points",
                         xytext=(0, 8),
                         ha='center',
                         fontsize=7,
                         fontweight='bold')

        # Линия среднего винрейта
        avg_winrate = daily_stats_sorted['Винрейт %'].mean()
        ax2.axhline(y=avg_winrate, color='red', linestyle='--', alpha=0.7,
                    label=f'Средний: {avg_winrate:.1f}%')

        ax2.legend(fontsize=8)
        plt.tight_layout()
        st.pyplot(fig2)

        # ГРАФИК 3: СОВМЕЩЕННЫЙ ГРАФИК (ПРИБЫЛЬ И WINRATE) - стиль из вашего кода
        st.subheader("Совмещенный анализ: Прибыль и Winrate")

        fig3, ax3 = plt.subplots(figsize=(10, 5))  # Уменьшенный размер

        # Две оси Y
        ax3_profit = ax3
        ax3_winrate = ax3.twinx()

        # Столбцы прибыли/убытка
        colors = ['#4CAF50' if x >= 0 else '#F44336' for x in daily_stats_sorted['Чистая прибыль']]
        bars = ax3_profit.bar(daily_stats_sorted['Дата_стр'], daily_stats_sorted['Чистая прибыль'],
                              color=colors, alpha=0.6, label='Прибыль/Убыток')

        # Линия винрейта
        line = ax3_winrate.plot(daily_stats_sorted['Дата_стр'], daily_stats_sorted['Винрейт %'],
                                color='#FF9800', linewidth=2, marker='s', markersize=3,
                                label='Winrate')

        # Настройки осей
        ax3_profit.set_xlabel('Дата', fontsize=10)
        ax3_profit.set_ylabel('Прибыль/Убыток (₽)', color='black', fontsize=10)
        ax3_winrate.set_ylabel('Winrate (%)', color='#FF9800', fontsize=10)

        ax3_profit.tick_params(axis='y', labelcolor='black', labelsize=8)
        ax3_winrate.tick_params(axis='y', labelcolor='#FF9800', labelsize=8)
        ax3_profit.tick_params(axis='x', rotation=45, labelsize=8)

        ax3_profit.set_title('Совмещенный анализ: Прибыль/Убыток и Winrate', fontsize=12, fontweight='bold')
        ax3_profit.grid(True, alpha=0.3)

        # Линия нуля для прибыли
        ax3_profit.axhline(y=0, color='black', linestyle='-', alpha=0.3)

        # Объединяем легенды
        lines1, labels1 = ax3_profit.get_legend_handles_labels()
        lines2, labels2 = ax3_winrate.get_legend_handles_labels()
        ax3_profit.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=8)

        plt.tight_layout()
        st.pyplot(fig3)

    else:
        st.info("Нет данных для построения графиков")

    # Дополнительная информация в двух колонках
    st.markdown("---")
    st.header("ℹ️ Дополнительная информация")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Распределение по типам пари")
        pari_type_counts = df_filtered['pari_type'].value_counts()
        if len(pari_type_counts) > 0:
            fig4, ax4 = plt.subplots(figsize=(6, 4))
            pari_type_counts.plot(kind='bar', ax=ax4, alpha=0.7, color='#2196F3')
            ax4.set_title('Типы пари', fontsize=10, fontweight='bold')
            ax4.tick_params(axis='x', rotation=45, labelsize=8)
            ax4.tick_params(axis='y', labelsize=8)
            ax4.grid(True, alpha=0.3)
            plt.tight_layout()
            st.pyplot(fig4)
        else:
            st.info("Нет данных")

    with col2:
        st.subheader("Распределение по результатам")
        result_counts = df_filtered['result'].value_counts()
        if len(result_counts) > 0:
            fig5, ax5 = plt.subplots(figsize=(6, 4))
            colors = ['#4CAF50' if 'Выигрыш' in str(x) else '#F44336' if 'Проигрыш' in str(x) else '#9E9E9E' for x in
                      result_counts.index]
            bars = result_counts.plot(kind='bar', ax=ax5, color=colors, alpha=0.7)
            ax5.set_title('Результаты ставок', fontsize=10, fontweight='bold')
            ax5.tick_params(axis='x', rotation=45, labelsize=8)
            ax5.tick_params(axis='y', labelsize=8)
            ax5.grid(True, alpha=0.3)

            # Добавляем значения на столбцы
            for i, (label, value) in enumerate(result_counts.items()):
                ax5.text(i, value, f'{value}', ha='center', va='bottom', fontsize=8)

            plt.tight_layout()
            st.pyplot(fig5)
        else:
            st.info("Нет данных")

    # Статистика по типам ставок
    st.subheader("Статистика по типам ставок")
    type_stats = df_filtered.groupby('pari_type').agg({
        'net_profit': 'sum',
        'stake_amount': 'sum',
        'coupon_number': 'count',
        'result': lambda x: (x == 'Выигрыш').sum()
    }).reset_index()

    type_stats.columns = ['Тип пари', 'Чистая прибыль', 'Оборот', 'Всего ставок', 'Выигрышных']
    type_stats['Винрейт %'] = (type_stats['Выигрышных'] / type_stats['Всего ставок'] * 100).round(1)

    st.dataframe(
        type_stats.style.format({
            'Чистая прибыль': '{:,.0f} ₽',
            'Оборот': '{:,.0f} ₽',
            'Всего ставок': '{:,.0f}',
            'Выигрышных': '{:,.0f}',
            'Винрейт %': '{:.1f}%'
        }),
        use_container_width=True
    )

    # Сырые данные
    st.markdown("---")
    st.header("📋 Исходные данные")

    with st.expander("Показать исходные данные"):
        # Сортируем исходные данные по дате (свежие сверху)
        df_sorted = df_filtered.sort_values('start_time', ascending=False)
        st.dataframe(df_sorted, use_container_width=True)

        # Кнопка для скачивания отфильтрованных данных
else:
    st.error("Не удалось загрузить данные. Убедитесь, что файл 'fon_bet_data2.csv' находится в правильной директории.")

# Информация о расчетах
st.sidebar.markdown("---")
st.sidebar.header("📝 Методика расчетов")
st.sidebar.markdown("""
**Чистая прибыль рассчитывается как:**
- ✅ Выигрыш: `win_amount - stake_amount`
- ❌ Проигрыш: `-stake_amount`
- 📊 Продано: `win_amount - stake_amount`
- 🔄 Возврат: `0`

**Винрейт:** процент выигрышных ставок от общего количества
""")