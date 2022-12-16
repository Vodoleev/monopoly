from telebot import types
from queue import Queue
import config
import random
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import os
import shutil
import time


class Street:
    def __init__(self, name):
        self.name = name
        self.cost = 0
        self.house_cost = 0
        self.hotel_cost = 0
        self.rent = []


class Special:
    def __init__(self, name):
        self.name = name
        self.cost = 0
        self.rent = []


class Extra:
    def __init__(self, name):
        self.name = name
        self.cost = 0
        self.rent = []


def processing(streets_path, game):
    with open(streets_path, 'r', encoding='utf-8') as streets:
        for line in streets:
            street = line.strip().split(sep=':')
            if street[0] == 'name':
                new_street = Street(street[1].strip())
            elif street[0] == 'cost':
                new_street.cost = int(street[1])
            elif street[0] == 'house_cost':
                new_street.house_cost = int(street[1])
            elif street[0] == 'hotel_cost':
                new_street.hotel_cost = int(street[1])
            elif street[0] == 'rent':
                rents = street[1].split(sep=',')
                new_street.rent = list(map(int, rents))
                game.streets.append(new_street)
            elif street[0] == 'special':
                new_special = Special(street[1].strip())
            elif street[0] == 's_cost':
                new_special.cost = int(street[1])
            elif street[0] == 's_rent':
                s_rents = street[1].split(sep=',')
                new_special.rent = list(map(int, s_rents))
                game.streets.append(new_special)
            elif street[0] == 'extra':
                new_extra = Extra(street[1].strip())
            elif street[0] == 'e_cost':
                new_extra.cost = int(street[1])
            elif street[0] == 'e_rent':
                e_rents = street[1].split(sep=',')
                new_extra.rent = list(map(int, e_rents))
                game.streets.append(new_extra)


def erode(cycles, image):
    for _ in range(cycles):
        image = image.filter(ImageFilter.MinFilter(3))
    return image


class User:
    def __init__(self, bot, chat, message, name):
        self.bot = bot
        self.chat_id = chat
        self.message_id = message
        self.name = name
        self.score = 0
        self.balance = 1500
        self.move_number = 0
        self.game_session = None
        self.property = {}
        self.prison = 0

    def send_current_game(self):
        flag = True
        photo = 'https://www.ejin.ru/wp-content/uploads/2020/03/19-3-scaled.jpg'
        text = ''
        keyboard = []
        if self.game_session is None:
            text = 'Привет'
            keyboard = [('Начать игру', 'start_game'), ('Правила', 'rules')]
        elif self.game_session == 'waiting':
            text = 'Вы добавлены в очередь'
        else:
            text = 'Информация по игре :\n'
            for i in range(len(self.game_session.users)):
                text += 'Имя : {}; Баланс: {}\n'.format(self.game_session.users[i].name,
                                                        self.game_session.users[i].balance)

            if self.game_session.current_user == self.move_number:
                photo = open('./img/{}/field.jpg'.format(id(self.game_session)), 'rb')
                if self.prison > 0:
                    self.prison -= 1
                    text = 'Вам осталось отбывать свой срок {} ходов'.format(self.prison)
                    keyboard = []
                    self.edit_message(photo, text, keyboard)
                    time.sleep(7)
                    self.game_session.next_player()
                    self.game_session.next_move()
                    print(self.name, self.balance, self.property)
                else:
                    text += 'Сейчас ваш ход'
                    keyboard = [('Бросить кубик', 'dice')]
            else:
                photo = open('./img/{}/field.jpg'.format(id(self.game_session)), 'rb')
                text += 'Сейчас ход игрока {}'.format(self.game_session.users[self.game_session.current_user].name)
        self.edit_message(photo, text, keyboard)

    def edit_message(self, photo='', text='', keyboard=[]):
        self.bot.edit_message_media(media=types.InputMedia(type='photo', media=photo, caption=text),
                                    chat_id=self.chat_id, message_id=self.message_id,
                                    reply_markup=create_inline_keyboard(keyboard))

    def send_message(self, photo='', text='', keyboard=[]):
        self.bot.send_photo(self.chat_id, photo=photo, caption=text, reply_markup=create_inline_keyboard(keyboard),
                            parse_mode="Markdown")

    def __str__(self):
        return str(self.chat_id) + ' ' + str(self.message_id) + ' ' + str(self.name) + ' ' + str(self.score)

    def rent_count(self, card):
        if card >= 22 and card <= 25:
            return self.ex_rent_count(card)
        if card >= 26:
            return self.sp_rent_count(card)
        else:
            return self.st_rent_count(card)

    def st_rent_count(self, card):
        flag = self.game_session.is_str_kit(card, self.move_number)
        if flag:
            home_count = self.property[card]
            return self.game_session.game.streets[card].rent[home_count + 1]
        else:
            return self.game_session.game.streets[card].rent[0]

    def sp_rent_count(self, card):
        complect = self.game_session.special_extra_kit(card, self.move_number)
        ans = self.game_session.game.streets[card].rent[complect - 1] * random.randint(2, 12)
        return ans

    def ex_rent_count(self, card):
        complect = self.game_session.special_extra_kit(card, self.move_number)
        return self.game_session.game.streets[card].rent[complect - 1]

    def can_buy_house(self):
        complects = self.game_session.is_any_kit(self.move_number)
        if len(complects) == 0:
            return None
        else:
            ans = []
            for kit in complects:
                min_count = 5
                for street in kit:
                    min_count = min(min_count, self.property[street])
                for street in kit:
                    if self.property[street] == min_count:
                        ans.append(street)
            return ans

    def name_and_house(self, streets):
        answer = []
        for street in streets:
            st = [street, self.game_session.game.streets[street].name, self.property[street] + 1,
                  str(self.game_session.game.streets[street].house_cost)]
            answer.append(st)
        return answer


class Game:
    def __init__(self, size):
        self.game_size = size
        self.users = Queue()
        self.sessions = set()
        self.streets = []
        self.kits = [{0, 1}, {2, 3, 4}, {5, 6, 7}, {8, 9, 10}, {11, 12, 13}, {14, 15, 16}, {17, 18, 19}, {20, 21},
                     {22, 23, 24, 25}, {26, 27}]

    def add_user(self, user):
        if user.game_session != 'waiting':
            user.game_session = 'waiting'
            self.users.put(user)
            if self.users.qsize() >= self.game_size:
                print('Создалась сессия')
                self.sessions.add(GameSession(self, self.users, config.GAME_SIZE))
                return True
        return False

    def get_kit(self, card):
        for kit in self.kits:
            if card in kit:
                return kit


class GameSession:
    def __init__(self, game, q, size):
        self.game = game
        self.users = []
        self.street_status = [None] * 28
        self.current_user = 0
        self.winner = None
        for i in range(size):
            self.users.append(q.get())
            self.users[-1].game_session = self
            self.users[-1].move_number = i
            print(self.users[-1].game_session)
        self.next_move()

    def is_str_kit(self, card, user_id):
        complect = self.game.get_kit(card)
        for number in complect:
            if self.street_status[number] != user_id:
                return False
        return True

    def is_any_kit(self, user_id):
        complects = []
        for card in self.users[user_id].property:
            if self.is_str_kit(card, user_id):
                complect = self.game.get_kit(card)
                complects.append(complect)
        return complects

    def special_extra_kit(self, card, user_id):
        complect = self.game.get_kit(card)
        ans = 0
        for number in complect:
            if self.street_status[number] == user_id:
                ans += 1
        return ans

    def next_move(self):

        if self.is_finish():
            print('winner')
            self.users[self.winner].edit_message('https://pro-voinu.ru/wp-content/uploads/2022/01/scale_1200.jpg',
                                                 'Вы победили!',
                                                 [('Вернуться в меню', 'start_menu')])
            for i in range(len(self.users)):
                if i != self.winner:
                    self.users[i].edit_message('http://photos.lifeisphoto.ru/187/0/1875984.jpg',
                                               'Победил ' + self.users[self.winner].name,
                                               [('Вернуться в меню', 'start_menu')])
            self.clear_game()
            return
        self.update_messages()

    def get_field(self):
        back = Image.open(config.FIELD_PATH)
        draw = ImageDraw.Draw(back)
        width = (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 9
        for user_id in range(len(self.users)):
            t, b, l, r = 0, 0, 0, 0
            i = self.users[user_id].score
            if i // 10 == 0:
                t, b = config.FIELD_INTERIOR[1], config.FIELD_EXTERNAL[1]
                if i % 10 == 0:
                    l = config.FIELD_INTERIOR[1]
                    r = config.FIELD_EXTERNAL[1]
                else:
                    t += config.HOME_WIDTH
                    r = config.FIELD_INTERIOR[1] - width * (i % 10)
                    l = r + width
            elif i // 10 == 1:
                l, r = config.FIELD_EXTERNAL[0], config.FIELD_INTERIOR[0]
                if i % 10 == 0:
                    t = config.FIELD_INTERIOR[1]
                    b = config.FIELD_EXTERNAL[1]
                else:
                    r -= config.HOME_WIDTH
                    t = config.FIELD_INTERIOR[1] - width * (i % 10)
                    b = t + width
            elif i // 10 == 2:
                t, b = config.FIELD_EXTERNAL[0], config.FIELD_INTERIOR[0]
                if i % 10 == 0:
                    l = config.FIELD_EXTERNAL[0]
                    r = config.FIELD_INTERIOR[0]
                else:
                    b -= config.HOME_WIDTH
                    r = config.FIELD_INTERIOR[0] + width * (i % 10)
                    l = r - width
            elif i // 10 == 3:
                l, r = config.FIELD_INTERIOR[1], config.FIELD_EXTERNAL[1]
                if i % 10 == 0:
                    t = config.FIELD_EXTERNAL[0]
                    b = config.FIELD_INTERIOR[0]
                else:
                    l += config.HOME_WIDTH
                    t = config.FIELD_INTERIOR[0] + width * (i % 10)
                    b = t - width

            mid = ((l + r) // 2, (t + b) // 2)
            if self.users[user_id].move_number == 0:
                chip1 = Image.open(config.CHIP1_PATH).resize((config.CHIP_SIZE, config.CHIP_SIZE))
                threshold = 0
                chip1_mask = erode(0, chip1.convert('L').point(lambda x: 255 if x > threshold else 0)).convert('L')
                back.paste(chip1, ((l + mid[0] - config.CHIP_SIZE) // 2, (mid[1] + t - config.CHIP_SIZE) // 2),
                           chip1_mask)
                # draw.rectangle((l, t, mid[0], mid[1]), fill='pink', outline="red")  # нулевой игрок
            elif self.users[user_id].move_number == 1:
                chip2 = Image.open(config.CHIP2_PATH).resize((config.CHIP_SIZE, config.CHIP_SIZE))
                threshold = 0
                chip2_mask = erode(0, chip2.convert('L').point(lambda x: 255 if x > threshold else 0)).convert('L')
                back.paste(chip2, ((mid[0] + r - config.CHIP_SIZE) // 2, (mid[1] + t - config.CHIP_SIZE) // 2),
                           chip2_mask)
                # draw.rectangle((mid[0], mid[1], r, t), fill='yellow', outline="red")  # первый игрок
            elif self.users[user_id].move_number == 2:
                chip3 = Image.open(config.CHIP3_PATH).resize((config.CHIP_SIZE, config.CHIP_SIZE))
                threshold = 0
                chip3_mask = erode(0, chip3.convert('L').point(lambda x: 255 if x > threshold else 0)).convert('L')
                back.paste(chip3, ((mid[0] + l - config.CHIP_SIZE) // 2, (mid[1] + b - config.CHIP_SIZE) // 2),
                           chip3_mask)
                # draw.rectangle((l, b, mid[0], mid[1]), fill='blue', outline="red")  # второй игрок
            elif self.users[user_id].move_number == 3:
                chip4 = Image.open(config.CHIP4_PATH).resize((config.CHIP_SIZE, config.CHIP_SIZE))
                threshold = 0
                chip4_mask = erode(0, chip4.convert('L').point(lambda x: 255 if x > threshold else 0)).convert('L')
                back.paste(chip4, ((mid[0] + mid[1] - config.CHIP_SIZE) // 2, (r + b - config.CHIP_SIZE) // 2),
                           chip4_mask)
                # draw.rectangle((mid[0], mid[1], r, b), fill='green', outline="red")  # третий игрок

        streets_img = Image.open(config.street_img_path)
        mid = (config.FIELD_INTERIOR[0] + config.FIELD_INTERIOR[1]) // 2

        # font = ImageFont.load("arial.pil")
        font = ImageFont.truetype("./comici.ttf", 30)
        for user_id in range(len(self.users)):
            if user_id == 0:
                draw.text((config.FIELD_INTERIOR[0] + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 4,
                           config.FIELD_INTERIOR[0] + 10), self.users[user_id].name, font=font, fill=('#1C0606'))
            elif user_id == 1:
                draw.text((mid + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 4,
                           config.FIELD_INTERIOR[0] + 10), self.users[user_id].name, font=font, fill=('#1C0606'))
            elif user_id == 2:
                draw.text((config.FIELD_INTERIOR[0] + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 4,
                           config.FIELD_INTERIOR[0] + 10 + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 2),
                          self.users[user_id].name, font=font, fill=('#1C0606'))
            elif user_id == 3:
                draw.text((mid + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 4,
                           config.FIELD_INTERIOR[0] + 10 + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[0]) // 2),
                          self.users[user_id].name, font=font, fill=('#1C0606'))

        house = Image.open(config.house_img_path).resize((config.house_size, config.house_size))
        threshold = 0
        house_mask = erode(0, house.convert('L').point(lambda x: 255 if x > threshold else 0)).convert('L')
        for user_id in range(len(self.users)):
            counter = 0
            for user_street in self.users[user_id].property:
                crop_street = streets_img.crop(config.street_img_edge[user_street])
                width = config.street_size
                height = int((width / crop_street.size[0]) * crop_street.size[1])
                crop_street = crop_street.resize((width, height))
                num_houses = self.users[user_id].property[user_street]
                #num_houses = random.randint(1, 5)
                for i in range(num_houses):
                    crop_street.paste(house, (i * config.house_size, 0), house_mask)
                if user_id == 0:
                    back.paste(crop_street,
                               (config.FIELD_INTERIOR[0] + config.street_lenght + config.street_lenght * (counter % 4) +
                                crop_street.size[
                                    0] * (counter % 4),
                                config.FIELD_INTERIOR[0] + config.name_pedding + (counter // 4) * config.street_lenght +
                                crop_street.size[
                                    1] * (counter // 4)))
                elif user_id == 1:
                    back.paste(crop_street,
                               (mid + config.street_lenght + config.street_lenght * (counter % 4) + crop_street.size[
                                   0] * (counter % 4),
                                config.FIELD_INTERIOR[0] + config.name_pedding + (counter // 4) * config.street_lenght +
                                crop_street.size[
                                    1] * (counter // 4)))
                elif user_id == 2:
                    back.paste(crop_street,
                               (config.FIELD_INTERIOR[0] + config.street_lenght + config.street_lenght * (counter % 4) +
                                crop_street.size[
                                    0] * (counter % 4),
                                config.FIELD_INTERIOR[0] + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[
                                    0]) // 2 + config.name_pedding + (counter // 4) * config.street_lenght +
                                crop_street.size[
                                    1] * (counter // 4)))
                elif user_id == 3:
                    back.paste(crop_street,
                               (mid + config.street_lenght + config.street_lenght * (counter % 4) + crop_street.size[
                                   0] * (counter % 4),
                                config.FIELD_INTERIOR[0] + (config.FIELD_INTERIOR[1] - config.FIELD_INTERIOR[
                                    0]) // 2 + config.name_pedding + (counter // 4) * config.street_lenght +
                                crop_street.size[
                                    1] * (counter // 4)))
                counter += 1
        if not os.path.isdir('./img/{}'.format(id(self))):
            os.mkdir('./img/{}'.format(id(self)))

        back.save('./img/{}/field.jpg'.format(id(self)))

    def update_messages(self):
        self.get_field()
        for i in range(len(self.users)):
            try:
                self.users[i].send_current_game()
            except:
                pass

    def is_finish(self):
        for i in range(len(self.users)):
            if self.users[i].balance < 0:
                max_bal = 0
                for i in range(len(self.users)):
                    max_bal = max(max_bal, self.users[i].balance)
                for i in range(len(self.users)):
                    if self.users[i].balance == max_bal:
                        self.winner = i
                        return True
        return False

    def next_player(self):
        self.current_user += 1
        self.current_user %= len(self.users)

    def clear_game(self):
        # Удаляем сессию из списка сессий, удаляем папку с полем и обнуляем характеристики пользователя
        shutil.rmtree('./img/{}'.format(id(self)))
        self.game.sessions.discard(self)
        for user in self.users:
            self.balance = 0
            self.game_session = None
            self.property = {}
            self.prison = 0
            user.game_session = None
            user.score = 0
            user.move_number = 0


def create_inline_keyboard(buttons):
    keyboard = types.InlineKeyboardMarkup()
    for button in buttons:
        button_name, button_ref = button
        new_button = types.InlineKeyboardButton(text=button_name, callback_data=button_ref, parse_mode='Markdown')
        keyboard.add(new_button)
    return keyboard


def create_start_menu(bot, message, chat_dict):
    text = 'Привет!'
    keyboard = [('Начать игру', 'start_game'), ('Правила', 'rules')]
    print('start')
    if message.chat.id not in chat_dict:
        chat_dict[message.chat.id] = User(bot=bot, chat=message.chat.id, message=0, name=message.from_user.username)
    else:
        if not (chat_dict[message.chat.id].game_session is None) and (
                chat_dict[message.chat.id].game_session != 'waiting'):
            text = 'Вы уже в игре'
            keyboard = [('Продолжить игру', 'continue_game'), ('Правила', 'rules')]
    chat_dict[message.chat.id].send_message('https://www.ejin.ru/wp-content/uploads/2020/03/19-3-scaled.jpg', text,
                                            keyboard)


def create_menu(bot, call, game, chat_dict):
    # Запоминаем нового пользователя
    if call.message.chat.id not in chat_dict:
        print('New user')
        chat_dict[call.message.chat.id] = User(bot=bot, chat=call.message.chat.id, message=call.message.id,
                                               name=call.from_user.username)
    # Обновляем текущеее сообщение от пользователя
    user = chat_dict[call.message.chat.id]
    if user.message_id != call.message.id and user.message_id != 0:
        try:
            bot.delete_message(call.message.chat.id, user.message_id)
        except:
            pass
    user.message_id = call.message.id

    # print(user, user.game_session)

    new_text = ''
    new_keyboard = []
    if call.data == 'start_game':
        print('start game')
        game.add_user(user)
        # print(user.game_session)
        try:
            user.send_current_game()
        except:
            pass
    elif call.data == 'start_menu':
        # Выводит стартовое меню
        if not (user.game_session is None):
            new_text = 'Вы уже в игре'
            new_keyboard = [('Продолжить игру', 'continue_game'), ('Правила', 'rules')]
        else:
            new_text = 'Привет'
            new_keyboard = [('Начать игру', 'start_game'), ('Правила', 'rules')]
        user.edit_message('https://www.ejin.ru/wp-content/uploads/2020/03/19-3-scaled.jpg', new_text, new_keyboard)
    elif call.data == 'rules':
        # Выводим правила
        new_text = config.RULES
        new_keyboard = [('Назад', 'start_menu')]
        user.edit_message('https://www.ejin.ru/wp-content/uploads/2020/03/19-3-scaled.jpg', new_text, new_keyboard)
    elif call.data == 'next':
        user.game_session.next_player()
        user.game_session.next_move()
        print(user.name, user.balance, user.property)
    elif call.data == 'buy':
        card_cost = game.streets[config.street_dict[user.score]].cost
        if (user.balance < card_cost):
            new_text = "У вас не хватает деняк, не получится купить поле"
        else:
            user.game_session.street_status[config.street_dict[user.score]] = user.move_number
            user.property[config.street_dict[user.score]] = 0
            user.balance -= card_cost
            new_text = ""
            print(user.name, user.balance, user.property)
        new_keyboard = [('Хочу купить здание', 'buy_house'), ('Закончить ход', 'next')]
        photo = open('./img/{}/field.jpg'.format(id(user.game_session)), 'rb')
        user.edit_message(photo, new_text, new_keyboard)
    elif call.data == 'not_buy':
        photo = open('./img/{}/field.jpg'.format(id(user.game_session)), 'rb')
        new_text = ""
        new_keyboard = [('Хочу купить здание', 'buy_house'), ('Закончить ход', 'next')]
        user.edit_message(photo, new_text, new_keyboard)

    elif call.data == 'buy_house':
        avaliable = user.can_buy_house()
        if avaliable is None:
            new_text = "У вас нет доступных домов для покупки, сначала соберите комплект"
            new_keyboard = [('Закончить ход', 'next')]
        else:
            options = user.name_and_house(avaliable)
            new_text = "Выберите, на какой улице хотите поставить дом\nВаш баланс: {}".format(user.balance)
            for option in options:
                button = 'Купить {} дом на {} за ${}'.format(option[1], str(option[2]), str(option[3]))
                new_keyboard.append((button, 'house {}'.format(str(option[0]))))
            new_keyboard.append('Я передумал', 'next')
        photo = open('./img/{}/field.jpg'.format(id(user.game_session)), 'rb')
        user.edit_message(photo, new_text, new_keyboard)

    elif call.data[:5] == 'house':
        street = call.data.split(sep=' ')
        user.property[street] += 1;
        new_keyboard = [('Хочу купить ещё здание', 'buy_house'), ('Закончить ход', 'next')]
        ############################################3

    elif call.data == 'dice':
        # Обработка хода игрока
        flag = True
        oldscore = user.score
        dice_value = random.randint(2, 12)
        user.score += dice_value
        user.score %= 40
        standart_string = "У вас выпало {}\n".format(dice_value)
        new_keyboard = [('Хочу купить здание', 'buy_house'), ('Закончить ход', 'next')]
        if oldscore > user.score:
            user.balance += 200
        if config.street_dict[user.score] == 'prize':
            prize = random.randint(10, 200)
            user.balance += prize
            new_text = standart_string + "Вы попали на призовое поле и выиграли ${}\nВаш баланс: ${}".format(str(prize),
                                                                                                             user.balance)
        elif config.street_dict[user.score] == 'penalty':
            penalty = random.randint(10, 200)
            user.balance -= penalty
            new_text = standart_string + "Вы попали на штрафное поле и заплатили ${} за превышение скорости\nВаш баланс: ${}".format(
                penalty, user.balance)
        elif config.street_dict[user.score] == 'tax':
            user.balance -= 200
            new_text = standart_string + "Вы попали на налоговое поле и заплатили $200 за лапки и хвосты\nВаш баланс: ${}".format(
                user.balance)
        elif config.street_dict[user.score] == 'super tax':
            user.balance -= 100
            new_text = standart_string + "Вы попали на СУПЕР налоговое поле и заплатили $100\nВаш баланс: ${}".format(
                user.balance)
        elif config.street_dict[user.score] == 'prison':
            new_text = standart_string + "Вы в зоопарке. Стойте. Наслаждайтесь)"
            pass
        elif config.street_dict[user.score] == 'relax':
            new_text = standart_string + "Вы легли на мягкий коврик. Отдыхайте)"
            pass
        elif config.street_dict[user.score] == 'start':
            new_text = standart_string + "Вы попали на стартовое поле и получили $200!\nВаш баланс: ${}".format(
                user.balance)
            pass
        elif config.street_dict[user.score] == 'go to prison':
            user.score = 10
            user.prison = 3
            user.balance -= 200
            new_text = standart_string + "Вас посадили в тюрьму, следующие 3 хода вы будете в одиночке"
        else:
            if user.game_session.street_status[config.street_dict[user.score]] == None:
                card_cost = game.streets[config.street_dict[user.score]].cost
                str_name = user.game_session.game.streets[config.street_dict[user.score]].name
                new_text = standart_string + "Вы попали на поле {}. Ваш баланс: ${}\nХотите купить это поле за ${}?".format(
                    str_name, user.balance, card_cost)
                new_keyboard = [('Купить за ${}!'.format(card_cost), 'buy'), ('Не хочу покупать', 'not_buy')]
            elif user.game_session.street_status[config.street_dict[user.score]] == user.move_number:
                str_name = user.game_session.game.streets[config.street_dict[user.score]].name
                new_text = standart_string + "Вы попали на своё поле {}. Ваш баланс: ${}".format(str_name, user.balance)
            else:
                owner = user.game_session.street_status[config.street_dict[user.score]]
                card = config.street_dict[user.score]
                rent = user.game_session.users[owner].rent_count(card)
                user.balance -= rent
                user.game_session.users[owner].balance += rent
                str_name = user.game_session.game.streets[config.street_dict[user.score]].name
                new_text = standart_string + "Вы попали на поле {} игрока {} и заплатили ему ${}\nТеперь ваш баланс: ${}".format(
                    str_name, user.game_session.users[owner].name, rent, user.balance)

        user.game_session.get_field()
        photo = open('./img/{}/field.jpg'.format(id(user.game_session)), 'rb')
        user.edit_message(photo, new_text, new_keyboard)

    elif call.data == 'continue_game':
        # Продолжаем игру
        if not (user.game_session is None):
            user.send_current_game()
