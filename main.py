import sqlite3
import telebot
from telebot import types

bot = telebot.TeleBot("7769584920:AAEDsY_x6leerOIP0930Z9iBdXBFZn0tVVY")
user_data = {}

ADMIN_IDS = [5237959867, 927652138]


def get_classes():
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT class FROM students')
    classes = cursor.fetchall()
    conn.close()
    return [class_[0] for class_ in classes]


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    classes = get_classes()
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for class_name in classes:
        keyboard.add(types.KeyboardButton(class_name))
    bot.send_message(message.chat.id, "Выберите класс:", reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text in get_classes())
def handle_class_selection(message):
    class_name = message.text
    user_data[message.chat.id] = {'class': class_name}
    show_students(message.chat.id, class_name)


def show_students(chat_id, class_name):
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, full_name FROM students WHERE class = ?', (class_name,))
    students = cursor.fetchall()
    conn.close()
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for student in students:
        keyboard.add(types.KeyboardButton(student[1]))
    if chat_id in ADMIN_IDS:
        keyboard.add(types.KeyboardButton("Сбросить оценки"))
        keyboard.add(types.KeyboardButton("Вывести все оценки"))
    keyboard.add(types.KeyboardButton("Назад"))
    bot.send_message(chat_id, f"Ученики класса {class_name}:", reply_markup=keyboard)


@bot.message_handler(func=lambda message: True)
def handle_student_and_grade(message):
    chat_id = message.chat.id
    if message.text == "Назад":
        send_welcome(message)
    elif message.text == "Сбросить оценки" and chat_id in ADMIN_IDS:
        class_name = user_data.get(chat_id, {}).get('class')
        if class_name is None:
            bot.send_message(chat_id, "Сначала выберите класс.")
            return
        reset_student_grades(chat_id, class_name)
    elif message.text == "Вывести все оценки" and chat_id in ADMIN_IDS:
        class_name = user_data.get(chat_id, {}).get('class')
        if class_name is None:
            bot.send_message(chat_id, "Сначала выберите класс.")
            return
        show_all_grades(chat_id, class_name)
    else:
        student_name = message.text.strip()
        show_student_grades(chat_id, student_name)


def update_student_grade(chat_id, student_id, action):
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    try:
        if action == "plus":
            cursor.execute('UPDATE students SET plus_count = plus_count + 1 WHERE id = ?', (student_id,))
        elif action == "minus":
            cursor.execute('UPDATE students SET minus_count = minus_count + 1 WHERE id = ?', (student_id,))
        conn.commit()
        bot.answer_callback_query(chat_id, "Оценка обновлена.")
    except sqlite3.Error as e:
        bot.answer_callback_query(chat_id, f"Ошибка базы данных: {e}")
    finally:
        conn.close()


def reset_student_grades(chat_id, class_name):
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    try:
        cursor.execute('UPDATE students SET plus_count = 0, minus_count = 0 WHERE class = ?', (class_name,))
        conn.commit()
        bot.send_message(chat_id, f"Оценки для класса {class_name} сброшены.")
    except sqlite3.Error as e:
        bot.send_message(chat_id, f"Ошибка базы данных: {e}")
    finally:
        conn.close()


def show_all_grades(chat_id, class_name):
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT full_name, plus_count, minus_count FROM students WHERE class = ?', (class_name,))
        students = cursor.fetchall()
        if not students:
            bot.send_message(chat_id, "В этом классе нет учеников.")
            return
        message = "Оценки всех учеников:\n"
        for student in students:
            full_name, plus, minus = student
            message += f"{full_name}: '+' = {plus}; '-' = {minus}\n"
        bot.send_message(chat_id, message)
    except sqlite3.Error as e:
        bot.send_message(chat_id, f"Ошибка базы данных: {e}")
    finally:
        conn.close()


def show_student_grades(chat_id, student_name):
    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT id, plus_count, minus_count FROM students WHERE full_name = ?', (student_name,))
        result = cursor.fetchone()
        if result is None:
            bot.send_message(chat_id, "Ученик не найден.")
            return
        student_id, plus, minus = result
        if chat_id in ADMIN_IDS:
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("+", callback_data=f"grade_{student_id}_plus"))
            keyboard.add(types.InlineKeyboardButton("-", callback_data=f"grade_{student_id}_minus"))
            bot.send_message(
                chat_id, f"Ученик: {student_name}\n'+' = {plus}\n'-' = {minus}",
                reply_markup=keyboard
            )
        else:
            bot.send_message(
                chat_id,
                f"{student_name}:\n+ {plus}\n- {minus}"
            )
    except sqlite3.Error as e:
        bot.send_message(chat_id, f"Ошибка базы данных: {e}")
    finally:
        conn.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith("grade_"))
def handle_grade_callback(call):
    chat_id = call.message.chat.id
    if chat_id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "У вас нет прав для этого действия.")
        return

    parts = call.data.split("_")
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Ошибка в данных.")
        return

    student_id = int(parts[1])
    action = parts[2]

    update_student_grade(call.id, student_id, action)

    conn = sqlite3.connect('school.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT full_name, plus_count, minus_count FROM students WHERE id = ?', (student_id,))
        result = cursor.fetchone()
        if result:
            full_name, plus, minus = result
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(types.InlineKeyboardButton("+", callback_data=f"grade_{student_id}_plus"))
            keyboard.add(types.InlineKeyboardButton("-", callback_data=f"grade_{student_id}_minus"))
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=call.message.message_id,
                text=f"{full_name}\n'+' = {plus}\n'-' = {minus}",
                reply_markup=keyboard
            )
        else:
            bot.answer_callback_query(call.id, "Ученик не найден.")
    except sqlite3.Error as e:
        bot.answer_callback_query(call.id, f"Ошибка базы данных: {e}")
    finally:
        conn.close()


if __name__ == '__main__':
    bot.polling()
