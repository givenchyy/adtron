require("dotenv").config();
const TelegramBot = require("node-telegram-bot-api");
const express = require("express");
const bodyParser = require("body-parser");
const db = require("./database"); // Убедитесь, что этот путь правильный

const token = process.env.TELEGRAM_BOT_TOKEN;
const bot = new TelegramBot(token, { polling: true });
const ADMIN_USER_ID = parseInt(process.env.ADMIN_USER_ID);
const postRequests = {}; // Хранение запросов на взаимные посты

// Функция для проверки прав на отправку сообщений
const checkIfBotCanPostMessages = async (channelName) => {
  const chatId = `@${channelName}`;
  console.log(`Checking permissions for bot in channel ${chatId}`);

  try {
    const chat = await bot.getChat(chatId);
    console.log(`Chat details:`, chat);

    const botInfo = await bot.getMe();
    console.log(`Bot ID: ${botInfo.id}`);

    const chatMember = await bot.getChatMember(chatId, botInfo.id);
    console.log(`Chat member status: ${chatMember.status}`);

    if (
      chatMember.status === "administrator" ||
      chatMember.status === "creator"
    ) {
      console.log(`Bot is an admin in ${chatId}`);
      return true;
    } else {
      console.log(`Bot is not an admin in ${chatId}`);
      return false;
    }
  } catch (error) {
    console.error(
      `Error getting chat member information for ${chatId}:`,
      error.message
    );
    return false;
  }
};

// Команды бота
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(
    msg.chat.id,
    "Привет! Я бот для взаимного обмена постами между каналами."
  );
});

bot.onText(/\/stats/, (msg) => {
  const userId = msg.from.id;
  const username = msg.from.username;

  db.getUserChannels(userId, (err, userChannels) => {
    if (err) {
      console.error(`Error getting user channels from database: ${err}`);
      bot.sendMessage(msg.chat.id, "Произошла ошибка при получении данных.");
      return;
    }

    if (!userChannels || userChannels.length === 0) {
      bot.sendMessage(
        msg.chat.id,
        "У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала."
      );
      return;
    }

    let response = `Личный кабинет для @${username}:\nПривязанные каналы:\n`;
    userChannels.forEach((channel, index) => {
      response += `${index + 1}. @${channel}\n`;
    });

    response += "\nДобавить канал: /addchannel @channel_name\n";
    response += "Удалить канал: /removechannel @channel_name\n";
    response += "Создать запрос на взаимный пост: /createpost\n";

    bot.sendMessage(msg.chat.id, response);
  });
});
bot.onText(/\/addchannel (.+)/, async (msg, match) => {
  const userId = msg.from.id;
  const channelName = match[1].replace("@", "");

  try {
    console.log(
      `Received request to add channel: @${channelName} for user ${userId}`
    );

    const canPostMessages = await checkIfBotCanPostMessages(channelName);

    if (canPostMessages) {
      // Добавляем канал в базу данных
      db.addUserChannel(userId, channelName, (err) => {
        if (err) {
          console.error(`Error adding channel to database: ${err}`);
          bot.sendMessage(
            msg.chat.id,
            "Ошибка при добавлении канала в базу данных."
          );
          return;
        }
        bot.sendMessage(
          msg.chat.id,
          `Канал @${channelName} привязан к вашему аккаунту.`
        );
      });
    } else {
      bot.sendMessage(
        msg.chat.id,
        `Пожалуйста, убедитесь, что я имею права администратора в канале @${channelName}.`
      );
    }
  } catch (error) {
    console.error("Error in /addchannel command:", error);
    bot.sendMessage(
      msg.chat.id,
      `Ошибка при добавлении канала: ${error.message}`
    );
  }
});

bot.onText(/\/removechannel (.+)/, (msg, match) => {
  const userId = msg.from.id;
  const channelName = match[1].replace("@", "");

  db.removeUserChannel(userId, channelName, (err) => {
    if (err) {
      bot.sendMessage(msg.chat.id, "Ошибка при удалении канала.");
      return;
    }
    bot.sendMessage(
      msg.chat.id,
      `Канал @${channelName} отвязан от вашего аккаунта.`
    );
  });
});

bot.onText(/\/createpost/, (msg) => {
  const userId = msg.from.id;

  // Получаем все привязанные каналы
  db.getAllChannels((err, allChannels) => {
    if (err) {
      console.error(`Error getting all channels from database: ${err}`);
      bot.sendMessage(msg.chat.id, "Ошибка при получении всех каналов.");
      return;
    }

    if (!allChannels || allChannels.length === 0) {
      bot.sendMessage(
        msg.chat.id,
        "Нет доступных каналов для создания запроса. Добавьте каналы с помощью /addchannel @channel_name."
      );
      return;
    }

    // Формируем клавиатуру для выбора канала
    const keyboard = allChannels.map((channel) => [
      { text: `@${channel}`, callback_data: `select_channel_${channel}` },
    ]);

    const opts = {
      reply_markup: {
        inline_keyboard: keyboard,
      },
    };

    bot.sendMessage(msg.chat.id, "Выберите канал для взаимного поста:", opts);
  });
});
bot.on("callback_query", async (query) => {
  const chatId = query.message.chat.id;
  const data = query.data;
  const userId = query.from.id;

  if (data.startsWith("select_channel_")) {
    const channelName = data.substring("select_channel_".length);
    postRequests[userId] = { channelName, postTemplate: null };
    bot.sendMessage(
      chatId,
      `Вы выбрали канал @${channelName}. Пожалуйста, отправьте шаблон поста.`
    );
    bot.deleteMessage(chatId, query.message.message_id);
  } else if (data.startsWith("confirm_") || data.startsWith("decline_")) {
    const [action, channelName, requesterId] = data.split("_", 3);
    if (action === "confirm") {
      // Обработка подтверждения
      const postTemplate = postRequests[requesterId]?.postTemplate;
      if (postTemplate) {
        const responseMessage = `${postTemplate}`;
        bot.sendMessage(`@${channelName}`, responseMessage);
        bot.sendMessage(
          requesterId,
          `Ваш запрос на взаимный пост был принят и опубликован в @${channelName}.`
        );
        db.updatePostRequest(
          requesterId,
          channelName,
          postTemplate,
          "confirmed",
          (err) => {
            if (err) {
              console.error("Ошибка при обновлении запроса:", err);
            }
          }
        );
      }
    } else {
      bot.sendMessage(
        requesterId,
        `Ваш запрос на взаимный пост от канала @${channelName} был отклонен.`
      );
    }
    bot.deleteMessage(chatId, query.message.message_id);
    delete postRequests[requesterId];
  }
});

bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  if (postRequests[chatId]) {
    const { channelName } = postRequests[chatId];
    postRequests[chatId].postTemplate = text;

    try {
      // Получаем имя канала отправителя
      const senderChannelName = await getChannelNameByUserId(chatId);

      // Получаем ID владельца канала
      const ownerId = await getChannelOwnerId(channelName);

      // Создаем клавиатуру для подтверждения или отклонения запроса
      const keyboard = [
        [
          {
            text: "Подтвердить",
            callback_data: `confirm_${channelName}_${chatId}`,
          },
          {
            text: "Отклонить",
            callback_data: `decline_${channelName}_${chatId}`,
          },
        ],
      ];
      const opts = { reply_markup: { inline_keyboard: keyboard } };

      // Отправляем сообщение владельцу канала для подтверждения запроса
      bot.sendMessage(
        ownerId,
        `Получен запрос на взаимный пост от канала @${senderChannelName}. Шаблон поста:\n\n${text}\n\nПодтвердите или отклоните запрос.`,
        opts
      );

      // Сохраняем запрос в базу данных
      db.addPostRequest(chatId, channelName, text, "pending", (err) => {
        if (err) {
          console.error("Error adding post request:", err);
        }
      });
    } catch (error) {
      console.error("Error in /createpost command:", error);
      bot.sendMessage(
        chatId,
        `Ошибка при создании запроса на пост: ${error.message}`
      );
    }
  }
});

async function getChannelOwnerId(channelName) {
  return new Promise((resolve, reject) => {
    // Здесь предполагается, что у вас есть функция, которая возвращает ID владельца канала по его имени
    // Возможно, вам нужно будет реализовать эту функцию в зависимости от вашей структуры данных
    db.getChannelOwnerId(channelName, (err, ownerId) => {
      if (err) {
        console.error("Ошибка при получении ID владельца канала:", err);
        reject("Неизвестный владелец канала");
      }
      resolve(ownerId);
    });
  });
}



// Запуск сервера
const app = express();
app.use(bodyParser.json());

app.get("/channels/:userId", (req, res) => {
  const userId = req.params.userId;
  db.getUserChannels(userId, (err, userChannels) => {
    if (err) {
      console.error("Error getting user channels:", err);
      res.status(500).send("Ошибка при получении данных.");
      return;
    }
    res.json(userChannels);
  });
});

app.post("/removeChannel", (req, res) => {
  const { userId, channel } = req.body;
  db.removeUserChannel(userId, channel, (err) => {
    if (err) {
      res.status(500).send("Ошибка при удалении канала.");
      return;
    }
    res.send("Канал удален");
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

// Запуск бота
bot.on("polling_error", console.log);

console.log("Bot and server are running...");
